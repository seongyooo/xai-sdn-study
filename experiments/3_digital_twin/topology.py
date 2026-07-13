"""
Mininet 토폴로지: 스위치 1개 + 호스트 3개
ONOS 컨트롤러(Docker)에 연결

실행 방법:
  sudo python3 topology.py
"""

import sys
import time
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.link import TCLink
from mininet.log import setLogLevel

ONOS_IP   = "127.0.0.1"
ONOS_PORT = 6653   # OpenFlow 포트


def create_topology():
    setLogLevel("info")

    net = Mininet(
        controller=RemoteController,
        switch=OVSSwitch,
        link=TCLink,
        autoSetMacs=True,
    )

    # 컨트롤러 (ONOS Docker)
    c0 = net.addController(
        "c0",
        controller=RemoteController,
        ip=ONOS_IP,
        port=ONOS_PORT,
    )

    # 스위치 (DPID → ONOS deviceId: of:0000000000000001, OpenFlow 1.3)
    s1 = net.addSwitch("s1", dpid="0000000000000001",
                       protocols="OpenFlow13")

    # 호스트
    h1 = net.addHost("h1", ip="10.0.0.1/24", mac="00:00:00:00:00:01")
    h2 = net.addHost("h2", ip="10.0.0.2/24", mac="00:00:00:00:00:02")
    h3 = net.addHost("h3", ip="10.0.0.3/24", mac="00:00:00:00:00:03")

    # 링크
    net.addLink(h1, s1, port2=1)
    net.addLink(h2, s1, port2=2)
    net.addLink(h3, s1, port2=3)

    net.start()
    print("\n토폴로지 시작됨. ONOS 연결 대기 중 (10초)...")
    time.sleep(10)

    return net, s1, h1, h2, h3


if __name__ == "__main__":
    net, s1, h1, h2, h3 = create_topology()
    print(f"\nh1 IP: {h1.IP()}, h2 IP: {h2.IP()}, h3 IP: {h3.IP()}")
    print("Mininet CLI 진입 (exit로 종료)")
    from mininet.cli import CLI
    CLI(net)
    net.stop()
