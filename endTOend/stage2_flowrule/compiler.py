"""
stage2_flowrule/compiler.py — IntentIR → ONOS FlowRule JSON 컴파일러

LLM 없이 결정론적으로 IntentIR을 ONOS REST API 형식의 FlowRule JSON으로 변환한다.
"""
from __future__ import annotations

import re
from typing import Optional

from models.intent_ir import IntentIR

# ── 서수 → 숫자 매핑 ──────────────────────────────────────────
SWITCH_ID_ORDINALS: dict[str, int] = {
    "first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5,
    "sixth": 6, "seventh": 7, "eighth": 8, "ninth": 9, "tenth": 10,
    "1st": 1, "2nd": 2, "3rd": 3, "4th": 4, "5th": 5,
    "6th": 6, "7th": 7, "8th": 8, "9th": 9, "10th": 10,
}

# ── ETH_TYPE 매핑 ─────────────────────────────────────────────
ETH_TYPE_MAP: dict[str, str] = {
    "ipv4": "0x800",
    "ipv6": "0x86DD",
    "arp": "0x806",
}

# ── IP_PROTO 매핑 ─────────────────────────────────────────────
IP_PROTO_MAP: dict[str, int] = {
    "tcp": 6,
    "udp": 17,
    "icmp": 1,
}

# ── 기본 우선순위 ─────────────────────────────────────────────
DEFAULT_PRIORITY: dict[str, int] = {
    "block": 50000,
    "forward": 32768,
    "qos": 40000,
    "sfc": 45000,
    "reroute": 40000,
}


class CompileError(ValueError):
    """FlowRule 컴파일 실패 시 발생"""
    pass


def extract_device_id(device_hint: str) -> str:
    """
    자연어 device_hint에서 ONOS device ID를 추출한다.

    지원 형식:
      - "switch 4" → "of:0000000000000004"
      - "s4" → "of:0000000000000004"
      - "node 2" → "of:0000000000000002"
      - "switch second" → "of:0000000000000002"
      - "of:0000000000000001" → 그대로 반환

    Raises:
        CompileError: 숫자를 파싱할 수 없는 경우
    """
    hint = device_hint.strip()

    # 이미 ONOS ID 형식이면 그대로 반환
    if re.match(r"^of:[0-9a-f]{16}$", hint, re.IGNORECASE):
        return hint.lower()

    # 숫자 직접 추출 (예: "switch 4", "s4", "sw2", "node 2")
    # \b 대신 (\d+) 사용 — "s2" 같은 경우 's'와 '2' 사이에 단어 경계가 없음
    num_match = re.search(r"(\d+)", hint)
    if num_match:
        num = int(num_match.group(1))
        return f"of:{num:016x}"

    # 서수 매핑 시도 (예: "switch second", "third node")
    hint_lower = hint.lower()
    for word, num in SWITCH_ID_ORDINALS.items():
        if word in hint_lower:
            return f"of:{num:016x}"

    raise CompileError(
        f"device_hint에서 스위치 번호를 파싱할 수 없습니다: '{device_hint}'"
    )


def _build_criteria(
    ir: IntentIR,
    in_port_override: Optional[int] = None,
    skip_src_ip: bool = False,
) -> list[dict]:
    """
    IntentIR에서 ONOS selector criteria 목록을 생성한다.

    Args:
        ir: IntentIR 객체
        in_port_override: ir.in_port 대신 사용할 IN_PORT 값
        skip_src_ip: IPV4_SRC criteria를 생략할지 여부 (SFC egress rule 등)
    """
    criteria: list[dict] = []
    eth_type_key = ir.eth_type  # None이면 ETH_TYPE criterion 생략

    # eth_type이 명시된 경우에만 ETH_TYPE criterion 추가
    # (port-only 룰에서 IPv4 한정 불필요한 제한 방지 — D10 fix)
    if eth_type_key:
        criteria.append({
            "type": "ETH_TYPE",
            "ethType": ETH_TYPE_MAP.get(eth_type_key, "0x800"),
        })
    elif ir.src_ip or ir.dst_ip or ir.ip_proto:
        # IP/프로토콜 필드가 있으면 ETH_TYPE 0x800 (IPv4) 암묵적으로 추가
        eth_type_key = "ipv4"
        criteria.append({
            "type": "ETH_TYPE",
            "ethType": "0x800",
        })

    in_port = in_port_override if in_port_override is not None else ir.in_port
    if in_port is not None:
        criteria.append({"type": "IN_PORT", "port": str(in_port)})

    if ir.vlan_id is not None:
        criteria.append({"type": "VLAN_VID", "vlanId": ir.vlan_id})

    if eth_type_key == "ipv4":
        if ir.src_ip and not skip_src_ip:
            criteria.append({"type": "IPV4_SRC", "ip": ir.src_ip})
        if ir.dst_ip:
            criteria.append({"type": "IPV4_DST", "ip": ir.dst_ip})
    elif eth_type_key is not None and ir.src_ip and not skip_src_ip:
        # ipv6/arp 등 기타 eth_type에서도 IP 필드 처리 (현재 미사용이지만 안전하게)
        pass

    if ir.ip_proto:
        criteria.append({"type": "IP_PROTO", "protocol": IP_PROTO_MAP[ir.ip_proto]})

    proto = ir.ip_proto
    if ir.src_port is not None:
        if proto == "udp":
            criteria.append({"type": "UDP_SRC", "udpPort": ir.src_port})
        else:
            criteria.append({"type": "TCP_SRC", "tcpPort": ir.src_port})

    if ir.dst_port is not None:
        if proto == "udp":
            criteria.append({"type": "UDP_DST", "udpPort": ir.dst_port})
        else:
            criteria.append({"type": "TCP_DST", "tcpPort": ir.dst_port})

    return criteria


def _make_flow(
    device_id: str,
    priority: int,
    criteria: list[dict],
    treatment: Optional[dict],
) -> dict:
    flow: dict = {
        "priority": priority,
        "timeout": 0,
        "isPermanent": "true",
        "deviceId": device_id,
        "selector": {"criteria": criteria},
    }
    if treatment is not None:
        flow["treatment"] = treatment
    return flow


def _parse_waypoint_port(waypoints: list, fallback: Optional[int]) -> Optional[str]:
    """
    waypoints 목록에서 첫 번째 포트 번호를 추출한다.
    형식: "switch 1:9", "s1:9", "of:0000000000000001:9", "9"
    fallback: waypoints가 없거나 파싱 불가 시 사용
    """
    if waypoints:
        wp = str(waypoints[0]).strip()
        # "xxx:PORT" 형식
        if ":" in wp:
            port_str = wp.rsplit(":", 1)[-1]
            if port_str.isdigit():
                return port_str
        # 숫자만
        if wp.isdigit():
            return wp
    if fallback is not None:
        return str(fallback)
    return None


def compile_flowrule(ir: IntentIR) -> dict:
    """
    IntentIR을 ONOS FlowRule JSON으로 변환한다.

    Returns:
        {"flows": [{...}]} 형식의 dict.
        sfc 액션은 flows 배열에 2개 이상의 룰을 포함할 수 있다.

    Raises:
        CompileError: device_id 파싱 실패 또는 필수 필드 누락
    """
    device_id = extract_device_id(ir.device_hint)
    priority = ir.priority if ir.priority is not None else DEFAULT_PRIORITY[ir.action]

    # ── block ─────────────────────────────────────────────────
    if ir.action == "block":
        criteria = _build_criteria(ir)
        treatment = {"instructions": [{"type": "NOACTION"}]}
        return {"flows": [_make_flow(device_id, priority, criteria, treatment)]}

    # ── forward ───────────────────────────────────────────────
    elif ir.action == "forward":
        criteria = _build_criteria(ir)
        out = str(ir.out_port) if ir.out_port is not None else "NORMAL"
        treatment = {"instructions": [{"type": "OUTPUT", "port": out}]}
        return {"flows": [_make_flow(device_id, priority, criteria, treatment)]}

    # ── qos ───────────────────────────────────────────────────
    elif ir.action == "qos":
        criteria = _build_criteria(ir)
        out = str(ir.out_port) if ir.out_port is not None else "NORMAL"
        instructions = [{"type": "OUTPUT", "port": out}]
        if ir.queue_id is not None:
            instructions.append({"type": "QUEUE", "queueId": ir.queue_id})
        treatment = {"instructions": instructions}
        return {"flows": [_make_flow(device_id, priority, criteria, treatment)]}

    # ── reroute ───────────────────────────────────────────────
    # reroute는 forward와 동일하되, alt_out_port를 우선 사용 (B2 fix: is not None 비교)
    elif ir.action == "reroute":
        criteria = _build_criteria(ir)
        out_port = ir.alt_out_port if ir.alt_out_port is not None else ir.out_port
        out = str(out_port) if out_port is not None else "NORMAL"
        treatment = {"instructions": [{"type": "OUTPUT", "port": out}]}
        return {"flows": [_make_flow(device_id, priority, criteria, treatment)]}

    # ── sfc ───────────────────────────────────────────────────
    elif ir.action == "sfc":
        # waypoint 포트 결정 (out_port 또는 waypoints에서 파싱)
        waypoint_port = _parse_waypoint_port(ir.waypoints or [], ir.out_port)
        if waypoint_port is None:
            raise CompileError(
                "sfc 액션에는 waypoints 또는 out_port(waypoint 포트)가 필요합니다."
            )

        # ingress rule: 매칭 트래픽 → waypoint 포트로 전송
        ingress_criteria = _build_criteria(ir)
        ingress_treatment = {"instructions": [{"type": "OUTPUT", "port": waypoint_port}]}
        ingress_flow = _make_flow(device_id, priority, ingress_criteria, ingress_treatment)

        # egress rule: waypoint에서 복귀 → 목적지로 전송
        # alt_out_port 미지정 시 CompileError — NORMAL은 운영상 위험 (D2 fix)
        if ir.alt_out_port is None:
            raise CompileError(
                "sfc action requires alt_out_port (egress port after waypoint). "
                "e.g. firewall at port 9, then forward to h1 -> alt_out_port=3"
            )
        alt_port = str(ir.alt_out_port)
        egress_criteria = _build_criteria(
            ir,
            in_port_override=int(waypoint_port),
            skip_src_ip=True,
        )
        # egress는 프로토콜/포트 매칭 불필요 (방화벽 통과 후 이미 검사됨)
        egress_criteria_minimal = [
            c for c in egress_criteria
            if c["type"] in ("ETH_TYPE", "IN_PORT", "IPV4_DST")
        ]
        egress_treatment = {"instructions": [{"type": "OUTPUT", "port": alt_port}]}
        egress_flow = _make_flow(
            device_id, priority - 1000, egress_criteria_minimal, egress_treatment
        )

        flows = [ingress_flow, egress_flow]

        result: dict = {"flows": flows}
        # sfc_chain 메타데이터 (ONOS에는 사용 안 하지만 XAI 설명용)
        if ir.waypoints:
            result["sfc_chain"] = ir.waypoints
        else:
            result["sfc_chain"] = [f"{device_id}:{waypoint_port}"]
        return result

    else:
        raise CompileError(f"지원하지 않는 action: '{ir.action}'")
