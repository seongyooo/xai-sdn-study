"""
models/topology.py — 네트워크 토폴로지 정의 및 엔티티 검증

다이아몬드 4-스위치 토폴로지를 정적으로 정의한다.
LLM 시스템 프롬프트에 주입하여 없는 호스트/스위치 생성(환각)을 억제하고,
파싱 결과를 토폴로지 인벤토리와 대조하여 unknown_entity 를 탐지한다.

ONOS API에서 동적으로 조회하는 옵션도 제공하며,
연결 실패 시 정적 다이아몬드 토폴로지로 폴백한다.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class NetworkTopology:
    """네트워크 토폴로지 — 호스트, 스위치, 포트 목록"""

    # 호스트: 이름 → IP 주소
    hosts: dict[str, str] = field(default_factory=dict)
    # 스위치: 이름 → ONOS device_id
    switches: dict[str, str] = field(default_factory=dict)
    # 포트: device_id → 포트 번호 목록
    ports: dict[str, list[int]] = field(default_factory=dict)

    # ── 정적 생성자 ────────────────────────────────────────────────

    @classmethod
    def diamond(cls) -> "NetworkTopology":
        """
        다이아몬드 4-스위치 토폴로지 (정적 정의).

        구성:
          h1(10.0.0.1), h2(10.0.0.2) → s1
          h3(10.0.0.3), h4(10.0.0.4) → s4
          s1 — s2 — s4  (저속 경로, 1 Mbps)
          s1 — s3 — s4  (고속 경로, 10 Mbps)
          s1 port 9     = 외부 방화벽/IDS 서비스 포인트 (SFC waypoint)
        """
        return cls(
            hosts={
                "h1": "10.0.0.1",
                "h2": "10.0.0.2",
                "h3": "10.0.0.3",
                "h4": "10.0.0.4",
            },
            switches={
                "s1": "of:0000000000000001",
                "s2": "of:0000000000000002",
                "s3": "of:0000000000000003",
                "s4": "of:0000000000000004",
            },
            ports={
                "of:0000000000000001": [1, 2, 3, 4, 9],  # s1: s2/s3/h1/h2/firewall
                "of:0000000000000002": [1, 2],            # s2: s1/s4
                "of:0000000000000003": [1, 2],            # s3: s1/s4
                "of:0000000000000004": [1, 2, 3, 4],     # s4: s2/s3/h3/h4
            },
        )

    @classmethod
    def from_onos(cls, client) -> "NetworkTopology":
        """
        ONOS REST API에서 토폴로지를 동적으로 조회한다.
        연결 실패 또는 빈 응답이면 정적 다이아몬드 토폴로지를 반환한다.
        """
        try:
            devices_resp = client.request("GET", "devices") or {}
            hosts_resp = client.request("GET", "hosts") or {}

            switches: dict[str, str] = {}
            ports_map: dict[str, list[int]] = {}

            for dev in devices_resp.get("devices", []):
                dev_id = dev["id"]
                # ONOS annotation name → 없으면 device_id 끝부분으로 추론
                name = dev.get("annotations", {}).get("name", "")
                if not name:
                    try:
                        n = int(dev_id.split(":")[-1], 16)
                        name = f"s{n}"
                    except Exception:
                        name = dev_id
                switches[name] = dev_id

                ports_resp = client.request("GET", f"devices/{dev_id}/ports") or {}
                port_nums: list[int] = []
                for p in ports_resp.get("ports", []):
                    try:
                        port_nums.append(int(p.get("port", 0)))
                    except (ValueError, TypeError):
                        pass
                ports_map[dev_id] = port_nums

            hosts: dict[str, str] = {}
            for host in hosts_resp.get("hosts", []):
                ips = host.get("ipAddresses", [])
                host_id = host.get("id", "")
                ann_name = host.get("annotations", {}).get("name", "")
                for ip in ips:
                    name = ann_name or host_id.split("/")[0]
                    hosts[name] = ip

            if switches:
                return cls(hosts=hosts, switches=switches, ports=ports_map)
        except Exception:
            pass  # 연결 실패 → 정적 토폴로지 폴백

        return cls.diamond()

    # ── 검증 메서드 ────────────────────────────────────────────────

    def known_ips(self) -> frozenset[str]:
        """토폴로지에 정의된 호스트 IP 집합 (CIDR 없이)"""
        return frozenset(self.hosts.values())

    def validate_ip(self, ip: Optional[str]) -> bool:
        """
        IP 주소(또는 CIDR)가 토폴로지 내 알려진 호스트 IP인지 확인.
        None이면 True (검증 대상 아님).
        """
        if ip is None:
            return True
        ip_only = str(ip).split("/")[0].strip()
        return ip_only in self.known_ips()

    def validate_switch(self, hint: Optional[str]) -> bool:
        """
        device_hint가 토폴로지 내 알려진 스위치를 가리키는지 확인.
        None이면 True (검증 대상 아님).

        지원 형식:
          - "of:0000000000000001" — ONOS device_id
          - "switch 4", "s4", "sw4", "node 4" — 숫자 추출 후 범위 확인
        """
        if hint is None:
            return True
        hint_s = str(hint).strip()

        # ONOS device_id 형식
        if re.match(r"^of:[0-9a-f]{16}$", hint_s, re.IGNORECASE):
            return hint_s.lower() in {v.lower() for v in self.switches.values()}

        # 이름 직접 매칭 (s1, s2 …)
        if hint_s.lower() in {k.lower() for k in self.switches}:
            return True

        # 숫자 추출 → 1 ~ N 범위 확인
        m = re.search(r"(\d+)", hint_s)
        if m:
            n = int(m.group(1))
            return 1 <= n <= len(self.switches)

        return False  # 알 수 없는 형식

    def check_intent(
        self,
        src_ip: Optional[str],
        dst_ip: Optional[str],
        device_hint: Optional[str],
    ) -> Optional[tuple[str, str]]:
        """
        인텐트 필드가 토폴로지와 일치하는지 확인한다.

        Returns:
            None — 검증 통과
            (rejection_reason, detail) — 검증 실패
        """
        if not self.validate_ip(src_ip):
            ip_only = str(src_ip).split("/")[0]
            return (
                "unknown_entity",
                f"src_ip '{ip_only}' is not a known host in the topology "
                f"(known: {', '.join(sorted(self.known_ips()))})",
            )

        if not self.validate_ip(dst_ip):
            ip_only = str(dst_ip).split("/")[0]
            return (
                "unknown_entity",
                f"dst_ip '{ip_only}' is not a known host in the topology "
                f"(known: {', '.join(sorted(self.known_ips()))})",
            )

        if not self.validate_switch(device_hint):
            return (
                "unknown_entity",
                f"device '{device_hint}' is not a known switch in the topology "
                f"(known: {', '.join(sorted(self.switches.keys()))})",
            )

        return None

    # ── LLM 프롬프트 텍스트 ───────────────────────────────────────

    def to_prompt_text(self) -> str:
        """
        LLM 시스템 프롬프트에 삽입할 토폴로지 컨텍스트.
        간결하게 유지하여 토큰 낭비를 최소화한다.
        """
        host_entries = ", ".join(
            f"{name}={ip}" for name, ip in sorted(self.hosts.items())
        )

        switch_lines = []
        for name, dev_id in sorted(self.switches.items()):
            port_list = sorted(self.ports.get(dev_id, []))
            port_str = ",".join(str(p) for p in port_list)
            switch_lines.append(f"    {name} (ports: {port_str})")

        switch_block = "\n".join(switch_lines)

        return (
            f"Network topology (ONLY reference entities listed here - do not invent others):\n"
            f"  Hosts: {host_entries}\n"
            f"  Switches:\n{switch_block}\n"
            f"  Special: s1 port 9 = firewall/IDS service point (SFC waypoint)\n"
            f"If the intent mentions a host IP or switch not in this list, "
            f"still parse as best you can; the pipeline will validate afterward."
        )
