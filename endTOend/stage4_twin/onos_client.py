"""
stage4_twin/onos_client.py — ONOS REST API 클라이언트

experiments/3_digital_twin/onos_client.py를 새 구조(config.py)에 맞게 재작성.
표준 라이브러리(urllib)만 사용하며 외부 의존성 없음.
"""
from __future__ import annotations

import base64
import json
import time
from typing import Any

import config


class OnosError(RuntimeError):
    """ONOS API 요청 실패 시 발생"""
    pass


class OnosClient:
    """ONOS REST API 최소 클라이언트"""

    def __init__(
        self,
        base_url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        timeout: float = 5.0,
    ) -> None:
        self.base_url = (base_url or config.ONOS_URL).rstrip("/")
        self.timeout = timeout
        _user = username or config.ONOS_USER
        _pass = password or config.ONOS_PASSWORD
        credentials = base64.b64encode(f"{_user}:{_pass}".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {credentials}",
            "Accept": "application/json",
        }

    def request(self, method: str, path: str, payload: Any | None = None) -> Any:
        """
        ONOS REST API 요청.

        Args:
            method: HTTP 메서드 ("GET", "POST", "DELETE" 등)
            path: API 경로 (예: "devices", "flows")
            payload: 요청 바디 (dict이면 JSON 직렬화)

        Returns:
            JSON 응답 파싱 결과 (응답 바디 없으면 None)

        Raises:
            OnosError: HTTP 오류 또는 연결 실패
        """
        from urllib.error import HTTPError, URLError
        from urllib.request import Request, urlopen

        data = None
        headers = dict(self.headers)
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = Request(
            f"{self.base_url}/{path.lstrip('/')}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                body = resp.read()
                if not body:
                    return None
                return json.loads(body.decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise OnosError(f"ONOS HTTP {exc.code}: {body[:300]}") from exc
        except URLError as exc:
            raise OnosError(f"ONOS 연결 실패: {exc.reason}") from exc

    def wait_until_ready(self, timeout: float = 120.0, interval: float = 2.0) -> None:
        """ONOS가 준비될 때까지 대기"""
        deadline = time.monotonic() + timeout
        last_error = "not ready"
        while time.monotonic() < deadline:
            try:
                self.request("GET", "devices")
                return
            except OnosError as exc:
                last_error = str(exc)
                time.sleep(interval)
        raise OnosError(
            f"ONOS가 {timeout:.0f}s 내에 준비되지 않음: {last_error}"
        )

    def devices(self) -> list[dict[str, Any]]:
        """등록된 OpenFlow 디바이스 목록 반환"""
        return self.request("GET", "devices").get("devices", [])

    def available_device_ids(self) -> set[str]:
        """available=True인 디바이스 ID 집합 반환"""
        return {
            d["id"]
            for d in self.devices()
            if d.get("available") is True and d.get("id")
        }

    def wait_for_devices(
        self,
        expected_ids: set[str],
        timeout: float = 60.0,
        interval: float = 2.0,
    ) -> set[str]:
        """expected_ids 디바이스가 모두 연결될 때까지 대기"""
        deadline = time.monotonic() + timeout
        available: set[str] = set()
        while time.monotonic() < deadline:
            available = self.available_device_ids()
            if expected_ids <= available:
                return available
            time.sleep(interval)
        missing = sorted(expected_ids - available)
        raise OnosError(f"ONOS 디바이스 연결 실패: {missing}")

    def deploy_flow_rules(self, payload: dict[str, Any]) -> None:
        """FlowRule 배포"""
        flows = payload.get("flows")
        if not isinstance(flows, list) or not flows:
            raise ValueError("payload에 비어있지 않은 'flows' 배열이 필요합니다.")
        self.request("POST", "flows", payload)

    def flows(self) -> list[dict[str, Any]]:
        """현재 설치된 모든 flow 반환"""
        return self.request("GET", "flows").get("flows", [])

    def delete_flow(self, device_id: str, flow_id: str) -> None:
        """특정 flow 삭제"""
        self.request("DELETE", f"flows/{device_id}/{flow_id}")

    def delete_flows_by_priority(self, priority: int) -> int:
        """특정 priority의 flow 전체 삭제. 삭제한 수 반환."""
        matches = [f for f in self.flows() if f.get("priority") == priority]
        for flow in matches:
            self.delete_flow(flow["deviceId"], flow["id"])
        return len(matches)

    def clear_app_flows(self, app_ids: list[str] | None = None) -> None:
        """특정 앱(또는 기본 앱)이 설치한 flow 전체 삭제"""
        if app_ids is None:
            app_ids = ["org.onosproject.rest", "org.onosproject.fwd"]
        for app_id in app_ids:
            try:
                self.request("DELETE", f"flows/application/{app_id}")
            except Exception:
                pass
