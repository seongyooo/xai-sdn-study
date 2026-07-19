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

    def wait_for_flow(
        self,
        device_id: str,
        priority: int,
        timeout: float = 15.0,
        interval: float = 1.0,
    ) -> None:
        """priority의 flow가 ADDED 상태로 설치될 때까지 대기"""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                all_flows = self.request("GET", f"flows/{device_id}").get("flows", [])
                for f in all_flows:
                    if f.get("priority") == priority and f.get("state") == "ADDED":
                        return
            except Exception:
                pass
            time.sleep(interval)
        # timeout 시에도 진행 (경고만)
        print(f"    [Twin] 경고: flow(priority={priority}) ADDED 상태 미확인 (계속 진행)")

    def activate_application(self, app_name: str) -> None:
        """ONOS 애플리케이션 활성화"""
        self.request("POST", f"applications/{app_name}/active")

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
        failed = 0
        for flow in matches:
            try:
                self.delete_flow(flow["deviceId"], flow["id"])
            except Exception as exc:
                failed += 1
                print(f"    [경고] flow {flow.get('id')} 삭제 실패: {exc}")
        if failed:
            print(f"    [경고] rollback 중 {failed}/{len(matches)}개 flow 삭제 실패 — ONOS에 잔류 가능")
        return len(matches) - failed

    def hosts(self) -> list[dict[str, Any]]:
        """등록된 호스트 목록 반환"""
        return self.request("GET", "hosts").get("hosts", [])

    def links(self) -> list[dict[str, Any]]:
        """토폴로지 링크 목록 반환"""
        return self.request("GET", "links").get("links", [])

    def port_statistics(self) -> list[dict[str, Any]]:
        """포트별 통계 반환"""
        return self.request("GET", "statistics/ports").get("statistics", [])

    def push_netcfg(self, payload: dict[str, Any]) -> None:
        """
        ONOS Network Configuration 푸시.
        devices/hosts/links 설정을 ONOS에 반영한다.
        실제 OpenFlow 연결 없이도 ONOS가 장치 메타데이터를 인식하게 된다.
        """
        self.request("POST", "network/configuration", payload)

    def clear_netcfg(self) -> None:
        """ONOS Network Configuration 초기화"""
        try:
            self.request("DELETE", "network/configuration")
        except Exception:
            pass

    def clear_app_flows(self, app_ids: list[str] | None = None) -> None:
        """특정 앱(또는 기본 앱)이 설치한 flow 전체 삭제"""
        if app_ids is None:
            app_ids = ["org.onosproject.rest", "org.onosproject.fwd"]
        for app_id in app_ids:
            try:
                self.request("DELETE", f"flows/application/{app_id}")
            except Exception:
                pass
