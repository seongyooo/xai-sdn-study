"""
stage3_static/schema_validator.py — ONOS FlowRule 스키마 검증

Pydantic v2 기반으로 ONOS FlowRule JSON의 구조적 유효성을 검사한다.
LLM 환각(hallucination)으로 인한 잘못된 필드 타입/값을 탐지한다.
"""
from __future__ import annotations

import re
from typing import Optional

from pydantic import BaseModel, field_validator, model_validator

# ── 허용 instruction types ─────────────────────────────────────
VALID_INSTRUCTION_TYPES: set[str] = {
    "OUTPUT", "DROP", "NOACTION", "TABLE", "GROUP",
    "METER", "QUEUE", "L0MODIFICATION", "L2MODIFICATION",
    "L3MODIFICATION", "L4MODIFICATION", "EXTENSION",
}

# ── 허용 criterion types ──────────────────────────────────────
VALID_CRITERION_TYPES: set[str] = {
    "IN_PORT", "IN_PHY_PORT", "ETH_DST", "ETH_SRC", "ETH_TYPE",
    "VLAN_VID", "VLAN_PCP", "IP_DSCP", "IP_ECN", "IP_PROTO",
    "IPV4_SRC", "IPV4_DST", "TCP_SRC", "TCP_DST",
    "UDP_SRC", "UDP_DST", "ICMPV4_TYPE", "ICMPV4_CODE",
    "IPV6_SRC", "IPV6_DST", "METADATA", "TUNNEL_ID",
}

DEVICE_ID_PATTERN = re.compile(r"^of:[0-9a-f]{16}$", re.IGNORECASE)


# ── Pydantic 모델 ──────────────────────────────────────────────

class _Criterion(BaseModel):
    type: str
    model_config = {"extra": "allow"}

    @field_validator("type")
    @classmethod
    def _validate_type(cls, v: str) -> str:
        if v not in VALID_CRITERION_TYPES:
            raise ValueError(
                f"알 수 없는 criterion type: '{v}'. "
                f"허용: {sorted(VALID_CRITERION_TYPES)}"
            )
        return v


class _Instruction(BaseModel):
    type: str
    model_config = {"extra": "allow"}

    @field_validator("type")
    @classmethod
    def _validate_type(cls, v: str) -> str:
        if v not in VALID_INSTRUCTION_TYPES:
            raise ValueError(
                f"알 수 없는 instruction type: '{v}'. "
                f"허용: {sorted(VALID_INSTRUCTION_TYPES)}"
            )
        return v


class _Selector(BaseModel):
    criteria: list[_Criterion]

    @field_validator("criteria")
    @classmethod
    def _not_empty(cls, v: list) -> list:
        if not v:
            raise ValueError("selector.criteria가 비어 있습니다.")
        return v


class _Treatment(BaseModel):
    instructions: list[_Instruction]


class _FlowRule(BaseModel):
    priority: int
    timeout: int = 0
    isPermanent: str = "true"
    deviceId: str
    selector: _Selector
    treatment: Optional[_Treatment] = None  # 없으면 암묵적 DROP

    model_config = {"extra": "allow"}

    @field_validator("priority")
    @classmethod
    def _priority_range(cls, v: int) -> int:
        if not (0 <= v <= 65535):
            raise ValueError(f"priority는 0~65535 범위여야 합니다. 현재: {v}")
        return v

    @field_validator("deviceId")
    @classmethod
    def _device_id_format(cls, v: str) -> str:
        if not DEVICE_ID_PATTERN.match(v):
            raise ValueError(
                f"deviceId 형식 오류: '{v}'. "
                f"올바른 형식: 'of:000000000000000X'"
            )
        return v

    @field_validator("isPermanent")
    @classmethod
    def _is_permanent_str(cls, v: str) -> str:
        if v not in ("true", "false"):
            raise ValueError(
                f"isPermanent는 'true' 또는 'false'여야 합니다. 현재: '{v}'"
            )
        return v


class _FlowRuleWrapper(BaseModel):
    flows: list[_FlowRule]


# ── 공개 검증 함수 ─────────────────────────────────────────────

def validate_schema(flowrule: dict) -> dict:
    """
    ONOS FlowRule JSON을 Pydantic으로 검증한다.

    Args:
        flowrule: {"flows": [...]} 또는 단일 flow dict

    Returns:
        {
            "valid": bool,
            "errors": [str]  # 오류 메시지 목록
        }
    """
    errors: list[str] = []

    # flows 배열 최상위 구조 확인
    if "flows" not in flowrule:
        errors.append("최상위에 'flows' 배열이 없습니다.")
        return {"valid": False, "errors": errors}

    if not isinstance(flowrule["flows"], list) or not flowrule["flows"]:
        errors.append("'flows' 배열이 비어 있거나 리스트가 아닙니다.")
        return {"valid": False, "errors": errors}

    try:
        _FlowRuleWrapper(**flowrule)
        return {"valid": True, "errors": []}
    except Exception as exc:
        # Pydantic v2 ValidationError는 .errors() 메서드 제공
        if hasattr(exc, "errors"):
            for err in exc.errors():
                loc = " → ".join(str(x) for x in err.get("loc", []))
                msg = err.get("msg", str(err))
                errors.append(f"[{loc}] {msg}" if loc else msg)
        else:
            errors.append(str(exc))
        return {"valid": False, "errors": errors}
