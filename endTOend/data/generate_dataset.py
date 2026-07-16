"""
generate_dataset.py — 신규 50케이스 생성 스크립트

기존 100케이스(sdn_intent-framework)를 복사하고
SFC 25케이스 + Reroute 25케이스를 추가하여
endTOend/data/intents_v2.jsonl (150케이스)을 생성한다.

토폴로지 (topology.py 기반):
  s1 (of:0000000000000001): port1→s2(slow), port2→s3(fast), port3→h1, port4→h2, port9→firewall
  s2 (of:0000000000000002): port1→s1, port2→s4
  s3 (of:0000000000000003): port1→s1, port2→s4
  s4 (of:0000000000000004): port1→s2, port2→s3, port3→h3, port4→h4

  h1=10.0.0.1, h2=10.0.0.2, h3=10.0.0.3, h4=10.0.0.4

사용법:
    cd endTOend/
    python data/generate_dataset.py
    # → endTOend/data/intents_v2.jsonl 생성
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# ── 경로 설정 ─────────────────────────────────────────────────────
_THIS_DIR = Path(__file__).resolve().parent
_ENDTOEND_DIR = _THIS_DIR.parent
_SOURCE_JSONL = Path(r"C:\Users\seonl\Desktop\c\2026\summer\sdn_intent-framework") \
    / "experiments" / "e1" / "data" / "intents.jsonl"
_OUTPUT_JSONL = _THIS_DIR / "intents_v2.jsonl"


# ── 헬퍼 ──────────────────────────────────────────────────────────

def _dev(n: int) -> str:
    """ONOS Device ID 생성: 1 → 'of:0000000000000001'"""
    return f"of:{n:016x}"


def _sel(
    src_ip: str | None = None,
    dst_ip: str | None = None,
    eth_type: str | None = "ipv4",
    protocol: str | None = None,
    src_port: int | None = None,
    dst_port: int | None = None,
    ingress_port: int | None = None,
) -> dict:
    return {
        "source": {"host": None, "ip": src_ip} if src_ip else None,
        "destination": {"host": None, "ip": dst_ip} if dst_ip else None,
        "eth_type": eth_type,
        "protocol": protocol,
        "source_port": src_port,
        "destination_port": dst_port,
        "ingress_port": ingress_port,
    }


def _enf(device_num: int, egress_port: str | None, set_vlan_id: int | None = None) -> dict:
    return {
        "device": _dev(device_num),
        "egress_port": egress_port,
        "set_vlan_id": set_vlan_id,
    }


def _fwd_rule(selector: dict, device_num: int, egress_port: str) -> dict:
    return {
        "intent_type": "forwarding",
        "action": "forward",
        "selector": selector,
        "qos": None,
        "enforcement": _enf(device_num, egress_port),
    }


def _sfc_rule(
    selector: dict,
    device_num: int,
    egress_port: str,
    sfc_role: str,
) -> dict:
    return {
        "intent_type": "sfc",
        "action": "forward",
        "selector": selector,
        "qos": None,
        "enforcement": _enf(device_num, egress_port),
        "sfc_role": sfc_role,
    }


def _reroute_rule(selector: dict, device_num: int, egress_port: str) -> dict:
    return {
        "intent_type": "reroute",
        "action": "forward",
        "selector": selector,
        "qos": None,
        "enforcement": _enf(device_num, egress_port),
    }


def _accepted(rules: list[dict], sfc_chain: list[str] | None = None) -> dict:
    program: dict = {"rules": rules}
    if sfc_chain:
        program["sfc_chain"] = sfc_chain
    return {"status": "accepted", "program": program, "rejection": None}


def _entry(
    case_id: str,
    category: str,
    variation: str,
    instruction: str,
    expected: dict,
) -> dict:
    return {
        "id": case_id,
        "cohort": "project",
        "category": category,
        "variation": variation,
        "instruction": instruction,
        "expected": expected,
    }


# ── SFC 케이스 정의 ───────────────────────────────────────────────

def _sfc_cases() -> list[dict]:
    cases = []

    # ── SFC-A: 단일 스위치 서비스 우회 (10케이스) ────────────────
    # s1:port9 = 방화벽. 패턴: ingress→port9, egress(in_port=9)→next_hop

    sfc_a = [
        # (id, instruction, src_ip, dst_ip, protocol, dst_port, egress_after_fw)
        ("SFC-A01",
         "Route HTTP from 10.0.0.1 to 10.0.0.3 through the firewall on switch 1 port 9.",
         "10.0.0.1", "10.0.0.3", "tcp", 80, "1"),   # h3 via s2(port1)
        ("SFC-A02",
         "Send all traffic from 10.0.0.2 to 10.0.0.4 via the firewall on switch 1.",
         "10.0.0.2", "10.0.0.4", None, None, "1"),
        ("SFC-A03",
         "Forward SSH traffic from 10.0.0.1 to 10.0.0.3 through port 9 of switch 1 for inspection.",
         "10.0.0.1", "10.0.0.3", "tcp", 22, "1"),
        ("SFC-A04",
         "Inspect ICMP from 10.0.0.3 to 10.0.0.1 using the security function at switch 1 port 9.",
         "10.0.0.3", "10.0.0.1", "icmp", None, "3"),  # h1 on s1:port3
        ("SFC-A05",
         "Route DNS traffic from 10.0.0.4 to 10.0.0.2 through the middlebox on port 9 of switch 1.",
         "10.0.0.4", "10.0.0.2", "udp", 53, "4"),   # h2 on s1:port4
        ("SFC-A06",
         "All HTTPS traffic from 10.0.0.1 to 10.0.0.4 must pass through the firewall at switch 1 port 9.",
         "10.0.0.1", "10.0.0.4", "tcp", 443, "1"),
        ("SFC-A07",
         "Redirect FTP from 10.0.0.2 to 10.0.0.3 through the inspection device on switch 1 port 9.",
         "10.0.0.2", "10.0.0.3", "tcp", 21, "1"),
        ("SFC-A08",
         "Enforce traffic from 10.0.0.1 to 10.0.0.3 to pass through port 9 of switch 1.",
         "10.0.0.1", "10.0.0.3", None, None, "1"),
        ("SFC-A09",
         "Send UDP traffic from 10.0.0.1 to 10.0.0.2 via security function at switch 1 port 9.",
         "10.0.0.1", "10.0.0.2", "udp", None, "4"),  # h2 on s1:port4
        ("SFC-A10",
         "Force all traffic from 10.0.0.4 to 10.0.0.1 through the firewall at port 9 of switch 1.",
         "10.0.0.4", "10.0.0.1", None, None, "3"),   # h1 on s1:port3
    ]

    for case_id, instr, src, dst, proto, dport, egress_after in sfc_a:
        rules = [
            _sfc_rule(
                _sel(src_ip=src, dst_ip=dst, protocol=proto, dst_port=dport),
                device_num=1, egress_port="9", sfc_role="ingress",
            ),
            _sfc_rule(
                _sel(dst_ip=dst, ingress_port=9),
                device_num=1, egress_port=egress_after, sfc_role="egress",
            ),
        ]
        cases.append(_entry(
            case_id, "sfc", "single_switch_bypass", instr,
            _accepted(rules, sfc_chain=[f"{_dev(1)}:9"]),
        ))

    # ── SFC-B: 다중 스위치 서비스 체인 (10케이스) ────────────────

    sfc_b_defs = [
        ("SFC-B01",
         "Route HTTP from 10.0.0.1 to 10.0.0.4 through switch 2 for deep packet inspection.",
         [
             _sfc_rule(_sel("10.0.0.1", "10.0.0.4", protocol="tcp", dst_port=80),
                       1, "1", "ingress"),  # s1→s2
             _sfc_rule(_sel(src_ip="10.0.0.1", dst_ip="10.0.0.4"),
                       2, "2", "transit"),  # s2→s4
         ],
         [f"{_dev(2)}"]),

        ("SFC-B02",
         "Forward all traffic from 10.0.0.2 to 10.0.0.4 via switch 2 as the IDS node.",
         [
             _sfc_rule(_sel("10.0.0.2", "10.0.0.4"), 1, "1", "ingress"),
             _sfc_rule(_sel(src_ip="10.0.0.2", dst_ip="10.0.0.4"), 2, "2", "transit"),
         ],
         [f"{_dev(2)}"]),

        ("SFC-B03",
         "Send TCP port 443 traffic from 10.0.0.1 to 10.0.0.3 through switch 2 for load balancing.",
         [
             _sfc_rule(_sel("10.0.0.1", "10.0.0.3", protocol="tcp", dst_port=443),
                       1, "1", "ingress"),
             _sfc_rule(_sel(dst_ip="10.0.0.3"), 2, "2", "transit"),
         ],
         [f"{_dev(2)}"]),

        ("SFC-B04",
         "Route ICMP from 10.0.0.1 to 10.0.0.4 through switch 3 for monitoring.",
         [
             _sfc_rule(_sel("10.0.0.1", "10.0.0.4", protocol="icmp"), 1, "2", "ingress"),
             _sfc_rule(_sel(dst_ip="10.0.0.4"), 3, "2", "transit"),
         ],
         [f"{_dev(3)}"]),

        ("SFC-B05",
         "Chain all traffic from 10.0.0.2 to 10.0.0.3 through switch 2 then switch 4.",
         [
             _sfc_rule(_sel("10.0.0.2", "10.0.0.3"), 1, "1", "ingress"),
             _sfc_rule(_sel(src_ip="10.0.0.2", dst_ip="10.0.0.3"), 2, "2", "transit"),
             _sfc_rule(_sel(dst_ip="10.0.0.3"), 4, "3", "egress"),
         ],
         [f"{_dev(2)}", f"{_dev(4)}"]),

        ("SFC-B06",
         "Apply IDS on switch 2 for HTTP traffic from 10.0.0.1 to 10.0.0.4, then deliver.",
         [
             _sfc_rule(_sel("10.0.0.1", "10.0.0.4", protocol="tcp", dst_port=80),
                       1, "1", "ingress"),
             _sfc_rule(_sel(dst_ip="10.0.0.4"), 2, "2", "egress"),
         ],
         [f"{_dev(2)}"]),

        ("SFC-B07",
         "Forward DNS from 10.0.0.3 to 10.0.0.1 via switch 3 for logging.",
         [
             _sfc_rule(_sel("10.0.0.3", "10.0.0.1", protocol="udp", dst_port=53),
                       4, "2", "ingress"),  # s4→s3
             _sfc_rule(_sel(dst_ip="10.0.0.1"), 3, "1", "egress"),  # s3→s1
         ],
         [f"{_dev(3)}"]),

        ("SFC-B08",
         "Route all UDP from 10.0.0.4 to 10.0.0.2 through switch 3.",
         [
             _sfc_rule(_sel("10.0.0.4", "10.0.0.2", protocol="udp"),
                       4, "2", "ingress"),  # s4→s3
             _sfc_rule(_sel(dst_ip="10.0.0.2"), 3, "1", "egress"),  # s3→s1
         ],
         [f"{_dev(3)}"]),

        ("SFC-B09",
         "Send FTP from 10.0.0.1 to 10.0.0.4 through switch 2 and switch 4.",
         [
             _sfc_rule(_sel("10.0.0.1", "10.0.0.4", protocol="tcp", dst_port=21),
                       1, "1", "ingress"),
             _sfc_rule(_sel(dst_ip="10.0.0.4"), 2, "2", "transit"),
             _sfc_rule(_sel(dst_ip="10.0.0.4"), 4, "4", "egress"),
         ],
         [f"{_dev(2)}", f"{_dev(4)}"]),

        ("SFC-B10",
         "Apply firewall on switch 1 then IDS on switch 2 for 10.0.0.1 to 10.0.0.4 traffic.",
         [
             _sfc_rule(_sel("10.0.0.1", "10.0.0.4"), 1, "9", "ingress"),
             _sfc_rule(_sel(dst_ip="10.0.0.4", ingress_port=9), 1, "1", "transit"),
             _sfc_rule(_sel(dst_ip="10.0.0.4"), 2, "2", "egress"),
         ],
         [f"{_dev(1)}:9", f"{_dev(2)}"]),
    ]

    for case_id, instr, rules, chain in sfc_b_defs:
        cases.append(_entry(
            case_id, "sfc", "multi_switch_chain", instr,
            _accepted(rules, sfc_chain=chain),
        ))

    # ── SFC-C: SFC + Security 결합 (5케이스) ─────────────────────

    sfc_c_defs = [
        ("SFC-C01",
         "Inspect traffic from 10.0.0.1 to 10.0.0.4 through port 9 of switch 1; drop if malicious.",
         [
             _sfc_rule(_sel("10.0.0.1", "10.0.0.4"), 1, "9", "ingress"),
             _sfc_rule(_sel(dst_ip="10.0.0.4", ingress_port=9), 1, "1", "egress"),
         ]),
        ("SFC-C02",
         "Route SMTP from 10.0.0.2 to 10.0.0.3 through the firewall; block if it fails inspection.",
         [
             _sfc_rule(_sel("10.0.0.2", "10.0.0.3", protocol="tcp", dst_port=25),
                       1, "9", "ingress"),
             _sfc_rule(_sel(dst_ip="10.0.0.3", ingress_port=9), 1, "1", "egress"),
         ]),
        ("SFC-C03",
         "Chain HTTP traffic from 10.0.0.1 through switch 2 IDS; forward clean traffic to 10.0.0.4.",
         [
             _sfc_rule(_sel("10.0.0.1", "10.0.0.4", protocol="tcp", dst_port=80),
                       1, "1", "ingress"),
             _sfc_rule(_sel(dst_ip="10.0.0.4"), 2, "2", "egress"),
         ]),
        ("SFC-C04",
         "Apply security inspection on switch 1 port 9 for all traffic from 10.0.0.1 to 10.0.0.4.",
         [
             _sfc_rule(_sel("10.0.0.1", "10.0.0.4"), 1, "9", "ingress"),
             _sfc_rule(_sel(dst_ip="10.0.0.4", ingress_port=9), 1, "1", "egress"),
         ]),
        ("SFC-C05",
         "Send SSH from 10.0.0.1 through firewall at switch 1 port 9 before allowing to 10.0.0.4.",
         [
             _sfc_rule(_sel("10.0.0.1", "10.0.0.4", protocol="tcp", dst_port=22),
                       1, "9", "ingress"),
             _sfc_rule(_sel(dst_ip="10.0.0.4", ingress_port=9), 1, "1", "egress"),
         ]),
    ]

    for case_id, instr, rules in sfc_c_defs:
        cases.append(_entry(
            case_id, "sfc", "sfc_security", instr,
            _accepted(rules, sfc_chain=[f"{_dev(1)}:9"]),
        ))

    return cases


# ── Reroute 케이스 정의 ───────────────────────────────────────────

def _reroute_cases() -> list[dict]:
    cases = []

    # ── Reroute-A: 대안 스위치 경유 (10케이스) ───────────────────

    rr_a_defs = [
        # (id, instruction, device_num, selector, egress_port)
        ("RR-A01",
         "Reroute traffic from 10.0.0.1 to 10.0.0.4 via switch 2 instead of switch 3.",
         1, _sel("10.0.0.1", "10.0.0.4"), "1"),

        ("RR-A02",
         "Redirect all traffic from 10.0.0.2 to 10.0.0.4 through switch 3 if switch 2 is down.",
         1, _sel("10.0.0.2", "10.0.0.4"), "2"),

        ("RR-A03",
         "Send 10.0.0.1 to 10.0.0.3 traffic via switch 3 to avoid switch 2 congestion.",
         1, _sel("10.0.0.1", "10.0.0.3"), "2"),

        ("RR-A04",
         "Reroute 10.0.0.3 to 10.0.0.1 packets through switch 2 to bypass switch 3.",
         4, _sel("10.0.0.3", "10.0.0.1"), "1"),

        ("RR-A05",
         "Redirect HTTP traffic from 10.0.0.1 to 10.0.0.4 via switch 2 for maintenance on switch 3.",
         1, _sel("10.0.0.1", "10.0.0.4", protocol="tcp", dst_port=80), "1"),

        ("RR-A06",
         "Reroute ICMP from 10.0.0.2 to 10.0.0.4 via switch 3 instead of switch 2.",
         1, _sel("10.0.0.2", "10.0.0.4", protocol="icmp"), "2"),

        ("RR-A07",
         "Redirect all traffic from 10.0.0.1 to 10.0.0.4 to use switch 2 path.",
         1, _sel("10.0.0.1", "10.0.0.4"), "1"),

        ("RR-A08",
         "Bypass switch 3: reroute 10.0.0.4 to 10.0.0.1 via switch 2.",
         4, _sel("10.0.0.4", "10.0.0.1"), "1"),

        ("RR-A09",
         "Reroute DNS from 10.0.0.4 to 10.0.0.2 through switch 2 instead of switch 3.",
         4, _sel("10.0.0.4", "10.0.0.2", protocol="udp", dst_port=53), "1"),

        ("RR-A10",
         "Force 10.0.0.2 to 10.0.0.3 traffic to take the switch 3 path, not switch 2.",
         1, _sel("10.0.0.2", "10.0.0.3"), "2"),
    ]

    for case_id, instr, dev, selector, port in rr_a_defs:
        cases.append(_entry(
            case_id, "reroute", "alt_switch", instr,
            _accepted([_reroute_rule(selector, dev, port)]),
        ))

    # ── Reroute-B: 특정 포트로 경로 변경 (8케이스) ───────────────

    rr_b_defs = [
        ("RR-B01",
         "On switch 1, redirect traffic destined for 10.0.0.4 from egress port 2 to port 1.",
         1, _sel(dst_ip="10.0.0.4"), "1"),

        ("RR-B02",
         "Change output port for 10.0.0.1 to 10.0.0.3 HTTP traffic on switch 1 to port 2.",
         1, _sel("10.0.0.1", "10.0.0.3", protocol="tcp", dst_port=80), "2"),

        ("RR-B03",
         "Reroute traffic entering port 1 of switch 2 to exit on port 2.",
         2, _sel(ingress_port=1, eth_type=None), "2"),

        ("RR-B04",
         "Redirect 10.0.0.2 to 10.0.0.4 traffic on switch 1 to use port 2 instead of port 1.",
         1, _sel("10.0.0.2", "10.0.0.4"), "2"),

        ("RR-B05",
         "On switch 4, change egress port for 10.0.0.3 to 10.0.0.1 traffic from port 1 to port 2.",
         4, _sel("10.0.0.3", "10.0.0.1"), "2"),

        ("RR-B06",
         "Switch 1: redirect HTTP from 10.0.0.1 to 10.0.0.3 to go out on port 1.",
         1, _sel("10.0.0.1", "10.0.0.3", protocol="tcp", dst_port=80), "1"),

        ("RR-B07",
         "Reroute UDP DNS traffic on switch 1 to exit port 2 instead of port 1.",
         1, _sel(protocol="udp", dst_port=53), "2"),

        ("RR-B08",
         "On switch 4, redirect traffic to 10.0.0.1 to port 2 instead of port 1.",
         4, _sel(dst_ip="10.0.0.1"), "2"),
    ]

    for case_id, instr, dev, selector, port in rr_b_defs:
        cases.append(_entry(
            case_id, "reroute", "port_change", instr,
            _accepted([_reroute_rule(selector, dev, port)]),
        ))

    # ── Reroute-C: 장애 우회 (7케이스) ───────────────────────────

    rr_c_defs = [
        ("RR-C01",
         "If switch 3 fails, redirect all 10.0.0.1 to 10.0.0.4 traffic through switch 2.",
         1, _sel("10.0.0.1", "10.0.0.4"), "1"),

        ("RR-C02",
         "Failover: send 10.0.0.2 to 10.0.0.4 via switch 2 when switch 3 link is unavailable.",
         1, _sel("10.0.0.2", "10.0.0.4"), "1"),

        ("RR-C03",
         "Emergency reroute: bypass switch 2 and send 10.0.0.1 to 10.0.0.3 traffic via switch 3.",
         1, _sel("10.0.0.1", "10.0.0.3"), "2"),

        ("RR-C04",
         "Reroute all traffic on switch 4 port 1 to exit via port 2 during maintenance.",
         4, _sel(ingress_port=1, eth_type=None), "2"),

        ("RR-C05",
         "Redirect 10.0.0.3 to 10.0.0.1 traffic from switch 4 via switch 2 if switch 3 is unreachable.",
         4, _sel("10.0.0.3", "10.0.0.1"), "1"),

        ("RR-C06",
         "Primary path down: reroute 10.0.0.1 to 10.0.0.4 traffic through switch 2 immediately.",
         1, _sel("10.0.0.1", "10.0.0.4"), "1"),

        ("RR-C07",
         "Backup path activation: send all TCP traffic from 10.0.0.2 to 10.0.0.4 via switch 3.",
         1, _sel("10.0.0.2", "10.0.0.4", protocol="tcp"), "2"),
    ]

    for case_id, instr, dev, selector, port in rr_c_defs:
        cases.append(_entry(
            case_id, "reroute", "failover", instr,
            _accepted([_reroute_rule(selector, dev, port)]),
        ))

    return cases


# ── 메인 ──────────────────────────────────────────────────────────

def main() -> int:
    # 1. 기존 100케이스 읽기
    if not _SOURCE_JSONL.exists():
        print(f"오류: 기존 데이터셋을 찾을 수 없습니다: {_SOURCE_JSONL}", file=sys.stderr)
        return 1

    existing: list[dict] = []
    with open(_SOURCE_JSONL, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                existing.append(json.loads(line))

    print(f"기존 케이스: {len(existing)}개")

    # 2. 신규 50케이스 생성
    new_cases = _sfc_cases() + _reroute_cases()
    print(f"신규 케이스: {len(new_cases)}개 (SFC {len(_sfc_cases())} + Reroute {len(_reroute_cases())})")

    # 3. 합치기
    all_cases = existing + new_cases
    print(f"총 케이스: {len(all_cases)}개")

    # 4. 출력
    _OUTPUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with open(_OUTPUT_JSONL, "w", encoding="utf-8") as f:
        for entry in all_cases:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    print(f"저장 완료: {_OUTPUT_JSONL}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
