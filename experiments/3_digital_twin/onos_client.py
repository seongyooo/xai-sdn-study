"""Minimal ONOS REST client used by the Digital Twin experiment."""

from __future__ import annotations

import base64
import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class OnosError(RuntimeError):
    """Raised when ONOS cannot satisfy an API request."""


class OnosClient:
    def __init__(
        self,
        base_url: str = "http://127.0.0.1:8181/onos/v1",
        username: str = "onos",
        password: str = "rocks",
        timeout: float = 5.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        credentials = base64.b64encode(f"{username}:{password}".encode()).decode()
        self.headers = {
            "Authorization": f"Basic {credentials}",
            "Accept": "application/json",
        }

    def request(self, method: str, path: str, payload: Any | None = None) -> Any:
        data = None
        headers = dict(self.headers)
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"

        request = Request(
            f"{self.base_url}/{path.lstrip('/')}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = response.read()
                if not body:
                    return None
                return json.loads(body.decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise OnosError(f"ONOS HTTP {exc.code}: {body[:300]}") from exc
        except URLError as exc:
            raise OnosError(f"ONOS connection failed: {exc.reason}") from exc

    def wait_until_ready(self, timeout: float = 120.0, interval: float = 2.0) -> None:
        deadline = time.monotonic() + timeout
        last_error = "not ready"
        while time.monotonic() < deadline:
            try:
                self.request("GET", "devices")
                return
            except OnosError as exc:
                last_error = str(exc)
                time.sleep(interval)
        raise OnosError(f"ONOS did not become ready within {timeout:.0f}s: {last_error}")

    def activate_application(self, app_name: str) -> None:
        self.request("POST", f"applications/{app_name}/active")

    def devices(self) -> list[dict[str, Any]]:
        return self.request("GET", "devices").get("devices", [])

    def available_device_ids(self) -> set[str]:
        return {
            device["id"]
            for device in self.devices()
            if device.get("available") is True and device.get("id")
        }

    def wait_for_devices(
        self, expected_ids: set[str], timeout: float = 60.0, interval: float = 2.0
    ) -> set[str]:
        deadline = time.monotonic() + timeout
        available: set[str] = set()
        while time.monotonic() < deadline:
            available = self.available_device_ids()
            if expected_ids <= available:
                return available
            time.sleep(interval)
        missing = sorted(expected_ids - available)
        raise OnosError(f"ONOS did not discover devices: {missing}")

    def deploy_flow_rules(self, payload: dict[str, Any]) -> None:
        flows = payload.get("flows")
        if not isinstance(flows, list) or not flows:
            raise ValueError("payload must contain a non-empty 'flows' list")
        self.request("POST", "flows", payload)

    def flows(self) -> list[dict[str, Any]]:
        return self.request("GET", "flows").get("flows", [])

    def delete_flow(self, device_id: str, flow_id: str) -> None:
        self.request("DELETE", f"flows/{device_id}/{flow_id}")

    def delete_flows_by_priority(self, priority: int) -> int:
        matches = [flow for flow in self.flows() if flow.get("priority") == priority]
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
