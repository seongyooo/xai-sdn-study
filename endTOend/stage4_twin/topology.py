"""
stage4_twin/topology.py — Mininet 토폴로지 빌더

두 가지 모드를 지원한다:
  1. build_network()            — 하드코딩된 다이아몬드 4-스위치 토폴로지 (기본값)
  2. build_network_from_custom() — data/custom_topology.json 기반 동적 토폴로지

Mininet 임포트는 이 파일을 임포트하는 순간이 아닌
각 build_* 함수 내부에서만 수행한다 (Linux 환경 체크 후 호출).
"""
from __future__ import annotations
from typing import Optional

EXPECTED_DEVICE_IDS: set[str] = {
    "of:0000000000000001",
    "of:0000000000000002",
    "of:0000000000000003",
    "of:0000000000000004",
}


def get_expected_device_ids(custom_data: Optional[dict] = None) -> set[str]:
    """토폴로지 데이터에서 예상 ONOS device ID 집합 반환."""
    if custom_data is None:
        return EXPECTED_DEVICE_IDS
    return {
        f"of:{sw.get('dpid', '0' * 16)}"
        for sw in custom_data.get("switches", [])
    }


def get_test_host_pairs(custom_data: Optional[dict] = None) -> tuple[tuple[str, str], tuple[str, str]]:
    """
    intent_check 및 regression 테스트에 사용할 호스트 쌍 반환.

    Returns:
        (primary_pair, regression_pair)
        primary_pair:    intent 검증 대상 (src, dst)
        regression_pair: 영향 없어야 할 쌍 (src, dst)
    """
    if custom_data is None:
        return ("h1", "h4"), ("h2", "h3")

    hosts = custom_data.get("hosts", [])
    ids = [h["id"] for h in hosts]

    if len(ids) >= 4:
        return (ids[0], ids[-1]), (ids[1], ids[2])
    if len(ids) == 2:
        return (ids[0], ids[1]), (ids[0], ids[1])
    if len(ids) >= 1:
        return (ids[0], ids[0]), (ids[0], ids[0])
    return ("h1", "h4"), ("h2", "h3")


def build_network_from_custom(
    custom_data: dict,
    controller_ip: str = "127.0.0.1",
    controller_port: int = 6653,
):
    """
    UI 에디터에서 저장한 커스텀 토폴로지 JSON → Mininet 네트워크.

    Args:
        custom_data: custom_topology.json 내용 dict
        controller_ip: ONOS 컨트롤러 IP
        controller_port: OpenFlow 포트

    Returns:
        Mininet 객체 (net.start() 호출 전)
    """
    try:
        from mininet.link import TCLink
        from mininet.net import Mininet
        from mininet.node import OVSSwitch, RemoteController
        from mininet.topo import Topo
    except ImportError as exc:
        raise RuntimeError(
            "Mininet이 설치되지 않았습니다. "
            "설치: sudo apt-get install mininet openvswitch-switch"
        ) from exc

    sw_ids  = {sw["id"] for sw in custom_data.get("switches", [])}
    host_ids = {h["id"] for h in custom_data.get("hosts", [])}

    class CustomTopo(Topo):
        def build(self):
            # 스위치
            for sw in custom_data.get("switches", []):
                self.addSwitch(
                    sw["id"],
                    dpid=sw.get("dpid", "0" * 16),
                    protocols="OpenFlow13",
                )
            # 호스트
            for h in custom_data.get("hosts", []):
                self.addHost(
                    h["id"],
                    ip=f"{h.get('ip', '10.0.0.1')}/24",
                    mac=h.get("mac", ""),
                )
            # 링크 (포트 번호는 Mininet이 자동 부여)
            port_counter: dict[str, int] = {}
            for lnk in custom_data.get("links", []):
                src, dst = lnk["source"], lnk["target"]
                if src not in sw_ids | host_ids or dst not in sw_ids | host_ids:
                    continue
                bw = lnk.get("bw")
                if bw:
                    self.addLink(src, dst, cls=TCLink, bw=bw)
                else:
                    self.addLink(src, dst)

    controller = RemoteController(
        "c0", ip=controller_ip, port=controller_port, protocols="tcp"
    )
    return Mininet(
        topo=CustomTopo(),
        controller=controller,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
        autoStaticArp=True,
    )


def build_network(controller_ip: str = "127.0.0.1", controller_port: int = 6653):
    """
    Mininet 다이아몬드 토폴로지를 생성하고 반환한다.

    Args:
        controller_ip: ONOS 컨트롤러 IP
        controller_port: OpenFlow 포트 (기본 6653)

    Returns:
        Mininet 객체 (net.start() 호출 전)

    Raises:
        RuntimeError: Mininet이 설치되지 않은 경우
    """
    try:
        from mininet.link import TCLink
        from mininet.net import Mininet
        from mininet.node import OVSSwitch, RemoteController
        from mininet.topo import Topo
    except ImportError as exc:
        raise RuntimeError(
            "Mininet이 설치되지 않았습니다. "
            "설치: sudo apt-get install mininet openvswitch-switch"
        ) from exc

    class DiamondTopo(Topo):
        def build(self):
            # 호스트 추가
            h1 = self.addHost("h1", ip="10.0.0.1/24")
            h2 = self.addHost("h2", ip="10.0.0.2/24")
            h3 = self.addHost("h3", ip="10.0.0.3/24")
            h4 = self.addHost("h4", ip="10.0.0.4/24")

            # 스위치 추가 (OpenFlow 1.3)
            s1 = self.addSwitch("s1", dpid="0000000000000001", protocols="OpenFlow13")
            s2 = self.addSwitch("s2", dpid="0000000000000002", protocols="OpenFlow13")
            s3 = self.addSwitch("s3", dpid="0000000000000003", protocols="OpenFlow13")
            s4 = self.addSwitch("s4", dpid="0000000000000004", protocols="OpenFlow13")

            # 호스트-스위치 연결
            self.addLink(h1, s1, port2=3)
            self.addLink(h2, s1, port2=4)
            self.addLink(h3, s4, port2=3)
            self.addLink(h4, s4, port2=4)

            # 스위치간 연결 (저속: s1-s2-s4 / 고속: s1-s3-s4)
            self.addLink(s1, s2, port1=1, port2=1, cls=TCLink, bw=1)
            self.addLink(s2, s4, port1=2, port2=1, cls=TCLink, bw=1)
            self.addLink(s1, s3, port1=2, port2=1, cls=TCLink, bw=10)
            self.addLink(s3, s4, port1=2, port2=2, cls=TCLink, bw=10)

    controller = RemoteController(
        "c0", ip=controller_ip, port=controller_port, protocols="tcp"
    )

    return Mininet(
        topo=DiamondTopo(),
        controller=controller,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
        autoStaticArp=True,
    )
