"""Mininet topology matching the IBNBench ONOS diamond topology."""

from __future__ import annotations


EXPECTED_DEVICE_IDS = {f"of:{number:016x}" for number in range(1, 5)}


def build_network(controller_ip: str = "127.0.0.1", controller_port: int = 6653):
    try:
        from mininet.link import TCLink
        from mininet.net import Mininet
        from mininet.node import OVSSwitch, RemoteController
        from mininet.topo import Topo
    except ImportError as exc:
        raise RuntimeError(
            "Mininet is not installed. Run: sudo apt-get install mininet openvswitch-switch"
        ) from exc

    class DiamondTopo(Topo):
        def build(self):
            h1 = self.addHost("h1", ip="10.0.0.1/24")
            h2 = self.addHost("h2", ip="10.0.0.2/24")
            h3 = self.addHost("h3", ip="10.0.0.3/24")
            h4 = self.addHost("h4", ip="10.0.0.4/24")

            s1 = self.addSwitch(
                "s1", dpid="0000000000000001", protocols="OpenFlow13"
            )
            s2 = self.addSwitch(
                "s2", dpid="0000000000000002", protocols="OpenFlow13"
            )
            s3 = self.addSwitch(
                "s3", dpid="0000000000000003", protocols="OpenFlow13"
            )
            s4 = self.addSwitch(
                "s4", dpid="0000000000000004", protocols="OpenFlow13"
            )

            self.addLink(h1, s1, port2=3)
            self.addLink(h2, s1, port2=4)
            self.addLink(h3, s4, port2=3)
            self.addLink(h4, s4, port2=4)
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
