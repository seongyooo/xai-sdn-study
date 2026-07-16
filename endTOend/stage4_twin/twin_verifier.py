"""
stage4_twin/twin_verifier.py — Digital Twin 기반 FlowRule 검증

Mininet 가상 네트워크를 사용해 FlowRule이 의도한 동작을 수행하는지
실제로 배포하고 테스트한다.

실행 조건:
  - Linux 플랫폼
  - root 권한 (sudo)
  - Mininet 설치됨

위 조건을 충족하지 못하면 status="skipped"로 반환한다.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class TwinResult:
    """Digital Twin 검증 결과"""

    status: str  # "passed" | "failed" | "skipped" | "error"
    reason: str = ""
    checks: dict = field(default_factory=dict)
    evidence: dict = field(default_factory=dict)

    def summary(self) -> str:
        status_map = {
            "passed": "PASS",
            "failed": "FAIL",
            "skipped": "SKIP",
            "error": "ERROR",
        }
        label = status_map.get(self.status, self.status.upper())
        if self.reason:
            return f"{label}: {self.reason}"
        return label


class TwinVerifier:
    """Mininet Digital Twin을 사용한 FlowRule 검증기"""

    def __init__(
        self,
        onos_url: Optional[str] = None,
        onos_user: Optional[str] = None,
        onos_password: Optional[str] = None,
        controller_ip: str = "127.0.0.1",
        controller_port: int = 6653,
    ) -> None:
        import config
        self.onos_url = onos_url or config.ONOS_URL
        self.onos_user = onos_user or config.ONOS_USER
        self.onos_password = onos_password or config.ONOS_PASSWORD
        self.controller_ip = controller_ip
        self.controller_port = controller_port

    def verify(self, flowrule: dict) -> TwinResult:
        """
        FlowRule을 Digital Twin에 배포하고 검증한다.

        검증 항목:
          1. baseline_connectivity: h1→h4 기본 연결성 (flowrule 배포 전)
          2. intent_check: flowrule의 의도 동작
             - block이면 타겟 pair ping 실패 확인
             - forward이면 타겟 pair ping 성공 확인
          3. regression: 관련 없는 host pair (h2↔h3) 영향 없음

        Args:
            flowrule: {"flows": [...]} 형식의 FlowRule dict

        Returns:
            TwinResult
        """
        # ── 플랫폼 체크 ────────────────────────────────────────
        skip_reason = self._check_platform()
        if skip_reason:
            return TwinResult(status="skipped", reason=skip_reason)

        from stage4_twin.onos_client import OnosClient, OnosError
        from stage4_twin.topology import build_network, EXPECTED_DEVICE_IDS

        client = OnosClient(
            base_url=self.onos_url,
            username=self.onos_user,
            password=self.onos_password,
        )

        # FlowRule에서 action 추출
        flows = flowrule.get("flows", [])
        flow = flows[0] if flows else {}
        # OUTPUT instruction이 있으면 forward, 없으면 block(DROP/NOACTION)
        instructions = flow.get("treatment", {}).get("instructions", [])
        has_output = any(i.get("type") == "OUTPUT" for i in instructions)
        action = "forward" if has_output else "block"

        # 타겟 pair 결정 (src_ip, dst_ip로 추정)
        criteria = flow.get("selector", {}).get("criteria", [])
        src_ip = None
        dst_ip = None
        for c in criteria:
            if c["type"] == "IPV4_SRC":
                src_ip = c.get("ip", "").split("/")[0]
            elif c["type"] == "IPV4_DST":
                dst_ip = c.get("ip", "").split("/")[0]

        # IP criteria가 없으면 테스트 대상 호스트를 특정할 수 없음 → skip
        # (VLAN-only, port-only 등 IP 주소 없는 룰 모두 해당)
        if src_ip is None and dst_ip is None:
            return TwinResult(
                status="skipped",
                reason="FlowRule에 IPV4_SRC/IPV4_DST criteria가 없어 트래픽 검증 대상을 특정할 수 없음",
            )

        # IP→호스트 매핑 (다이아몬드 토폴로지 기준)
        ip_to_host = {
            "10.0.0.1": "h1", "10.0.0.2": "h2",
            "10.0.0.3": "h3", "10.0.0.4": "h4",
        }
        src_host = ip_to_host.get(src_ip or "", "h1")
        dst_host = ip_to_host.get(dst_ip or "", "h4")

        net = None
        checks: dict = {}
        evidence: dict = {}

        try:
            # ── 1. ONOS 준비 대기 ──────────────────────────
            print("    [Twin] ONOS 준비 대기 중...")
            client.wait_until_ready(timeout=60.0)

            # ── 2. 필수 ONOS 앱 활성화 ────────────────────
            # OpenFlow 앱이 꺼져 있으면 스위치가 ONOS에 연결되지 않음
            print("    [Twin] ONOS OpenFlow 앱 활성화 중...")
            for app in [
                "org.onosproject.openflow-base",
                "org.onosproject.openflow",
                "org.onosproject.fwd",
            ]:
                try:
                    client.activate_application(app)
                except Exception:
                    pass  # 이미 활성화된 앱은 오류 무시
            time.sleep(2)

            # ── 3. 기존 flow 정리 ──────────────────────────
            print("    [Twin] 기존 flow 정리 중...")
            client.clear_app_flows()
            time.sleep(1)

            # ── 4. Mininet 토폴로지 시작 ───────────────────
            print("    [Twin] Mininet 토폴로지 시작 중...")
            net = build_network(self.controller_ip, self.controller_port)
            net.start()

            # 디바이스 연결 대기 (90초로 늘림 — 첫 연결은 오래 걸릴 수 있음)
            print("    [Twin] 디바이스 연결 대기 중...")
            client.wait_for_devices(EXPECTED_DEVICE_IDS, timeout=90.0)
            time.sleep(3)  # 프로액티브 flow 설치 대기

            # ── 4. baseline 연결성 확인 ────────────────────
            print("    [Twin] baseline 연결성 확인 중...")
            baseline_ok, baseline_msg = self._ping_check(
                net, "h1", "10.0.0.4", expect_reach=True
            )
            checks["baseline_connectivity"] = baseline_ok
            evidence["baseline_msg"] = baseline_msg

            # ── 5. FlowRule 배포 ───────────────────────────
            print("    [Twin] FlowRule 배포 중...")
            client.deploy_flow_rules(flowrule)
            # flow가 OVS에 실제 push될 때까지 대기 (ADDED 상태 확인)
            client.wait_for_flow(
                device_id=flow.get("deviceId", "of:0000000000000001"),
                priority=flow.get("priority", 50000),
                timeout=15.0,
            )

            # ── 6. intent 동작 확인 ────────────────────────
            # block이면 ping 실패, forward이면 ping 성공
            expect_reach = (action == "forward")
            intent_ok, intent_msg = self._ping_check(
                net, src_host, dst_ip or "10.0.0.4", expect_reach=expect_reach
            )
            checks["intent_check"] = intent_ok
            evidence["intent_msg"] = intent_msg

            # ── 7. 회귀 테스트 (h2↔h3) ───────────────────
            regression_ok, regression_msg = self._ping_check(
                net, "h2", "10.0.0.3", expect_reach=True
            )
            checks["regression"] = regression_ok
            evidence["regression_msg"] = regression_msg

            # ── 판정 ──────────────────────────────────────
            all_passed = all(checks.values())
            status = "passed" if all_passed else "failed"
            failed_checks = [k for k, v in checks.items() if not v]
            reason = (
                f"실패한 검사: {', '.join(failed_checks)}"
                if failed_checks
                else "모든 검사 통과"
            )

            return TwinResult(
                status=status,
                reason=reason,
                checks=checks,
                evidence=evidence,
            )

        except Exception as exc:
            return TwinResult(
                status="error",
                reason=f"Digital Twin 오류: {exc}",
                checks=checks,
                evidence=evidence,
            )

        finally:
            # ── 8. rollback ───────────────────────────────
            print("    [Twin] FlowRule rollback 중...")
            try:
                priority = flow.get("priority")
                if priority is not None:
                    client.delete_flows_by_priority(priority)
                else:
                    client.clear_app_flows()
            except Exception:
                pass

            # ── 9. Mininet 종료 ───────────────────────────
            if net is not None:
                print("    [Twin] Mininet 종료 중...")
                try:
                    net.stop()
                except Exception:
                    pass

    def _ping_check(
        self,
        net,
        src_host: str,
        dst_ip: str,
        expect_reach: bool,
    ) -> tuple[bool, str]:
        """
        src_host에서 dst_ip로 ping을 전송하고 결과를 확인한다.

        Args:
            net: Mininet 객체
            src_host: 소스 호스트 이름 (예: "h1")
            dst_ip: 대상 IP 주소 (예: "10.0.0.4")
            expect_reach: True이면 도달 가능해야 함, False이면 차단되어야 함

        Returns:
            (성공 여부, 설명 메시지)
        """
        try:
            host = net.get(src_host)
            # dst_ip 형식 검증 (shell injection 방지)
            if not re.match(r"^[\d.]+$", dst_ip):
                return False, f"잘못된 IP 형식: {dst_ip}"

            host.sendCmd(f"ping -c 3 -W 1 {dst_ip}")
            result = host.waitOutput()

            # "0% packet loss" in "100% packet loss" 가 True가 되는 버그 방지
            # → regex로 실제 packet loss % 추출
            m = re.search(r"(\d+)% packet loss", result)
            loss_pct = int(m.group(1)) if m else 100
            reachable = (loss_pct == 0)

            if expect_reach:
                success = reachable
                msg = (
                    f"{src_host}→{dst_ip} ping 성공 (예상: 도달 가능)"
                    if success
                    else f"{src_host}→{dst_ip} ping 실패 (예상: 도달 가능이어야 함)"
                )
            else:
                success = not reachable
                msg = (
                    f"{src_host}→{dst_ip} ping 차단됨 (예상: 차단)"
                    if success
                    else f"{src_host}→{dst_ip} ping 통과됨 (예상: 차단이어야 함)"
                )

            return success, msg

        except Exception as exc:
            return False, f"ping 실행 오류: {exc}"

    @staticmethod
    def _check_platform() -> str:
        """
        실행 환경을 확인하고 문제가 있으면 이유를 반환한다.
        문제 없으면 빈 문자열 반환.
        """
        if sys.platform != "linux":
            return f"플랫폼이 Linux가 아님 (현재: {sys.platform})"

        if os.geteuid() != 0:
            return "root 권한 없음 (sudo -E로 실행하세요)"

        try:
            subprocess.run(
                ["mn", "--version"],
                capture_output=True,
                check=True,
                timeout=5,
            )
        except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return "Mininet(mn)이 설치되지 않음"

        return ""  # 모든 조건 충족
