"""
models/intent_ir.py — 인텐트 중간 표현(Intermediate Representation)

LLM이 파싱한 자연어 인텐트를 구조화된 형태로 저장한다.
Stage1(인텐트 파싱) → Stage2(FlowRule 컴파일)의 교환 형식.
"""
from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, field_validator


class IntentIR(BaseModel):
    """SDN 인텐트의 구조화된 중간 표현"""

    action: Literal["forward", "block", "qos"]
    device_hint: str  # "switch 4", "node 2" 등 자연어 힌트

    # 5-튜플 매칭 필드
    src_ip: Optional[str] = None       # "10.0.0.1/32"
    dst_ip: Optional[str] = None
    src_port: Optional[int] = None
    dst_port: Optional[int] = None
    ip_proto: Optional[Literal["tcp", "udp", "icmp"]] = None

    # 포트 정보
    out_port: Optional[int] = None     # forward/qos 시 출력 포트
    in_port: Optional[int] = None      # 입력 포트 매칭

    # QoS / 우선순위
    priority: Optional[int] = None
    vlan_id: Optional[int] = None
    queue_id: Optional[int] = None

    # 이더넷 타입
    eth_type: Optional[Literal["ipv4", "ipv6", "arp"]] = "ipv4"

    @field_validator("src_ip", "dst_ip", mode="before")
    @classmethod
    def _normalize_ip(cls, v: Optional[str]) -> Optional[str]:
        """IP 주소에 /32 마스크가 없으면 추가. 유효한 IPv4가 아니면 None 반환."""
        if v is None:
            return v
        v = str(v).strip()
        if not v:
            return None

        # CIDR에서 IP 부분만 추출
        ip_part = v.split("/")[0]

        # 유효한 IPv4인지 확인 (숫자 4개가 점으로 구분)
        if not re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", ip_part):
            return None

        # /마스크가 없으면 /32 추가
        if "/" not in v:
            v = v + "/32"
        return v

    def to_dict(self) -> dict:
        """직렬화 (None 필드 제외)"""
        return {k: val for k, val in self.model_dump().items() if val is not None}

    @classmethod
    def from_llm_output(cls, raw: dict) -> "IntentIR":
        """
        LLM 출력 dict에서 안전하게 IntentIR 파싱.
        알 수 없는 필드나 잘못된 값은 무시하고 기본값으로 대체.
        """
        # action 정규화
        action_raw = str(raw.get("action", "forward")).lower().strip()
        if action_raw not in ("forward", "block", "qos"):
            # 의미적 매핑
            if any(w in action_raw for w in ("drop", "deny", "block", "reject")):
                action_raw = "block"
            elif any(w in action_raw for w in ("queue", "qos", "quality")):
                action_raw = "qos"
            else:
                action_raw = "forward"

        # device_hint 정규화 — null/"None"/빈값이면 기본값 "switch 1"
        device_hint_raw = raw.get("device_hint") or raw.get("device")
        if not device_hint_raw or str(device_hint_raw).strip().lower() in ("none", "null", ""):
            device_hint = "switch 1"
        else:
            device_hint = str(device_hint_raw).strip()

        # ip_proto 정규화
        proto_raw = raw.get("ip_proto")
        if proto_raw:
            proto_raw = str(proto_raw).lower().strip()
            if proto_raw not in ("tcp", "udp", "icmp"):
                proto_raw = None

        # eth_type 정규화
        eth_type_raw = raw.get("eth_type")
        if eth_type_raw:
            eth_type_raw = str(eth_type_raw).lower().strip()
            if eth_type_raw not in ("ipv4", "ipv6", "arp"):
                eth_type_raw = "ipv4"

        # 안전한 int 변환
        def _safe_int(val) -> Optional[int]:
            if val is None:
                return None
            try:
                return int(val)
            except (ValueError, TypeError):
                return None

        # IP 필드 — LLM이 non-null을 줬는데 유효한 IPv4가 아니면 오류
        # (조용히 None으로 변환하면 catch-all 룰이 만들어질 수 있음)
        _IP_PATTERN = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}")
        for _field in ("src_ip", "dst_ip"):
            _val = raw.get(_field)
            if _val is None:
                continue
            if not isinstance(_val, str):
                raise ValueError(
                    f"LLM이 {_field}에 문자열이 아닌 {type(_val).__name__} 값을 반환했습니다. "
                    f"IP 주소(예: 10.0.0.1)를 포함한 인텐트를 입력해주세요."
                )
            if not _IP_PATTERN.match(_val.split("/")[0]):
                raise ValueError(
                    f"LLM이 {_field}에 유효하지 않은 값 '{_val}'을 반환했습니다. "
                    f"IP 주소(예: 10.0.0.1)를 포함한 인텐트를 입력해주세요."
                )

        return cls(
            action=action_raw,
            device_hint=device_hint,
            src_ip=raw.get("src_ip") or None,
            dst_ip=raw.get("dst_ip") or None,
            src_port=_safe_int(raw.get("src_port")),
            dst_port=_safe_int(raw.get("dst_port")),
            ip_proto=proto_raw,
            out_port=_safe_int(raw.get("out_port")),
            in_port=_safe_int(raw.get("in_port")),
            priority=_safe_int(raw.get("priority")),
            vlan_id=_safe_int(raw.get("vlan_id")),
            queue_id=_safe_int(raw.get("queue_id")),
            eth_type=eth_type_raw or "ipv4",
        )
