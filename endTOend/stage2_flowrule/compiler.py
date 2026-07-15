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

    # 숫자 직접 추출 (예: "switch 4", "s4", "node 2")
    num_match = re.search(r"\b(\d+)\b", hint)
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


def compile_flowrule(ir: IntentIR) -> dict:
    """
    IntentIR을 ONOS FlowRule JSON으로 변환한다.

    Returns:
        {"flows": [{...}]} 형식의 dict

    Raises:
        CompileError: device_id 파싱 실패 등
    """
    device_id = extract_device_id(ir.device_hint)

    # ── 우선순위 결정 ──────────────────────────────────────────
    priority = ir.priority if ir.priority is not None else DEFAULT_PRIORITY[ir.action]

    # ── selector.criteria 구성 ─────────────────────────────────
    criteria: list[dict] = []

    # ETH_TYPE 항상 포함
    eth_type_key = ir.eth_type or "ipv4"
    criteria.append({
        "type": "ETH_TYPE",
        "ethType": ETH_TYPE_MAP.get(eth_type_key, "0x800"),
    })

    # IN_PORT
    if ir.in_port is not None:
        criteria.append({
            "type": "IN_PORT",
            "port": str(ir.in_port),
        })

    # VLAN_VID
    if ir.vlan_id is not None:
        criteria.append({
            "type": "VLAN_VID",
            "vlanId": ir.vlan_id,
        })

    # IP 주소 (IPv4일 때만)
    if eth_type_key == "ipv4":
        if ir.src_ip:
            criteria.append({
                "type": "IPV4_SRC",
                "ip": ir.src_ip,
            })
        if ir.dst_ip:
            criteria.append({
                "type": "IPV4_DST",
                "ip": ir.dst_ip,
            })

    # IP_PROTO
    if ir.ip_proto:
        criteria.append({
            "type": "IP_PROTO",
            "protocol": IP_PROTO_MAP[ir.ip_proto],
        })

    # 포트 (TCP/UDP 판별)
    proto = ir.ip_proto  # "tcp", "udp", "icmp", None
    if ir.src_port is not None:
        if proto == "udp":
            criteria.append({"type": "UDP_SRC", "udpPort": ir.src_port})
        else:
            # TCP 또는 프로토콜 미지정 시 TCP_SRC 기본
            criteria.append({"type": "TCP_SRC", "tcpPort": ir.src_port})

    if ir.dst_port is not None:
        if proto == "udp":
            criteria.append({"type": "UDP_DST", "udpPort": ir.dst_port})
        else:
            criteria.append({"type": "TCP_DST", "tcpPort": ir.dst_port})

    # ── treatment 구성 ────────────────────────────────────────
    treatment: Optional[dict] = None

    if ir.action == "block":
        # block → treatment 없음 (암묵적 DROP)
        treatment = None

    elif ir.action == "forward":
        instructions = []
        if ir.out_port is not None:
            instructions.append({
                "type": "OUTPUT",
                "port": str(ir.out_port),
            })
        else:
            # 출력 포트 미지정 시 NORMAL (일반 전달)
            instructions.append({
                "type": "OUTPUT",
                "port": "NORMAL",
            })
        treatment = {"instructions": instructions}

    elif ir.action == "qos":
        instructions = []
        out_port = ir.out_port if ir.out_port is not None else "NORMAL"
        instructions.append({
            "type": "OUTPUT",
            "port": str(out_port),
        })
        if ir.queue_id is not None:
            instructions.append({
                "type": "QUEUE",
                "queueId": ir.queue_id,
            })
        treatment = {"instructions": instructions}

    # ── FlowRule 조립 ─────────────────────────────────────────
    flow: dict = {
        "priority": priority,
        "timeout": 0,
        "isPermanent": "true",
        "deviceId": device_id,
        "selector": {
            "criteria": criteria,
        },
    }

    if treatment is not None:
        flow["treatment"] = treatment

    return {"flows": [flow]}
