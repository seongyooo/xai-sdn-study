"""
Step 1: JSON 스키마 검증 (Pydantic)
LLM이 생성한 FlowRule JSON의 구조적 오류 탐지
"""

import re
import json
from typing import Optional
from pydantic import BaseModel, field_validator, model_validator

# ── Pydantic 모델 정의 ──────────────────────────────────────

VALID_ETH_TYPES = {"0x800", "0x0800", "0x86dd", "0x86DD", "0x806", "0x0806"}
VALID_INSTRUCTION_TYPES = {"OUTPUT", "DROP", "QUEUE", "L2MODIFICATION", "METER", "TABLE"}
VALID_CRITERIA_TYPES = {
    "ETH_TYPE", "IPV4_SRC", "IPV4_DST", "IPV6_SRC", "IPV6_DST",
    "IP_PROTO", "TCP_SRC", "TCP_DST", "UDP_SRC", "UDP_DST",
    "IN_PORT", "ETH_SRC", "ETH_DST", "VLAN_VID", "ICMPV4_TYPE",
    "ICMPV4_CODE", "ARP_OP", "ARP_SPA", "ARP_TPA",
}
DEVICE_ID_PATTERN = re.compile(r"^of:[0-9a-f]{16}$")
IP_CIDR_PATTERN = re.compile(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}$")


class Criterion(BaseModel):
    type: str

    @field_validator("type")
    @classmethod
    def validate_type(cls, v):
        if v not in VALID_CRITERIA_TYPES:
            raise ValueError(f"알 수 없는 criteria type: '{v}'. LLM 환각 의심.")
        return v

    model_config = {"extra": "allow"}


class Selector(BaseModel):
    criteria: list[Criterion]

    @field_validator("criteria")
    @classmethod
    def validate_criteria_not_empty(cls, v):
        if not v:
            raise ValueError("selector.criteria가 비어 있습니다.")
        return v


class Instruction(BaseModel):
    type: str

    @field_validator("type")
    @classmethod
    def validate_type(cls, v):
        if v not in VALID_INSTRUCTION_TYPES:
            raise ValueError(f"알 수 없는 instruction type: '{v}'. LLM 환각 의심.")
        return v

    model_config = {"extra": "allow"}


class Treatment(BaseModel):
    instructions: list[Instruction]


class FlowRule(BaseModel):
    priority: int
    timeout: int = 0
    isPermanent: str = "true"
    deviceId: str
    selector: Selector
    treatment: Optional[Treatment] = None  # 없으면 DROP 규칙

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, v):
        if v < 0 or v > 65535:
            raise ValueError(f"priority는 0~65535 범위여야 합니다. 현재: {v}")
        return v

    @field_validator("deviceId")
    @classmethod
    def validate_device_id(cls, v):
        if not DEVICE_ID_PATTERN.match(v):
            raise ValueError(f"deviceId 형식 오류: '{v}'. 올바른 형식: 'of:000000000000000X'")
        return v

    @field_validator("isPermanent")
    @classmethod
    def validate_is_permanent(cls, v):
        if v not in ("true", "false"):
            raise ValueError(f"isPermanent는 'true' 또는 'false'여야 합니다. 현재: '{v}'")
        return v


class FlowRuleWrapper(BaseModel):
    """ONOS REST API는 flows 배열로 감싸서 전달"""
    flows: list[FlowRule]


# ── 검증 함수 ───────────────────────────────────────────────

def validate_flowrule(json_input) -> dict:
    """
    FlowRule JSON을 검증하고 결과 반환.

    Args:
        json_input: dict 또는 JSON 문자열

    Returns:
        {
            "valid": bool,
            "errors": [str],   # 오류 메시지 목록
            "parsed": FlowRule | None
        }
    """
    if isinstance(json_input, str):
        try:
            json_input = json.loads(json_input)
        except json.JSONDecodeError as e:
            return {"valid": False, "errors": [f"JSON 파싱 실패: {e}"], "parsed": None}

    errors = []

    # flows 래퍼 있는 경우 처리
    if "flows" in json_input:
        try:
            wrapper = FlowRuleWrapper(**json_input)
            return {"valid": True, "errors": [], "parsed": wrapper}
        except Exception as e:
            for err in e.errors() if hasattr(e, "errors") else [{"msg": str(e)}]:
                field = " → ".join(str(x) for x in err.get("loc", []))
                msg = err.get("msg", str(err))
                errors.append(f"[{field}] {msg}" if field else msg)
            return {"valid": False, "errors": errors, "parsed": None}

    # 단일 FlowRule인 경우
    try:
        rule = FlowRule(**json_input)
        return {"valid": True, "errors": [], "parsed": rule}
    except Exception as e:
        for err in e.errors() if hasattr(e, "errors") else [{"msg": str(e)}]:
            field = " → ".join(str(x) for x in err.get("loc", []))
            msg = err.get("msg", str(err))
            errors.append(f"[{field}] {msg}" if field else msg)
        return {"valid": False, "errors": errors, "parsed": None}


def generate_error_feedback(errors: list[str]) -> str:
    """검증 실패 시 LLM 재생성을 위한 오류 피드백 메시지 생성"""
    lines = ["다음 오류를 수정하여 ONOS FlowRule JSON을 다시 생성하세요:"]
    for i, err in enumerate(errors, 1):
        lines.append(f"  {i}. {err}")
    lines.append("\n올바른 deviceId 형식: 'of:000000000000000X' (X는 스위치 번호의 16진수)")
    lines.append("올바른 criteria type: ETH_TYPE, IPV4_SRC, IPV4_DST, IP_PROTO, TCP_DST, UDP_DST, IN_PORT 등")
    return "\n".join(lines)


# ── 테스트용 망가진 FlowRule 10개 ──────────────────────────

TEST_CASES = [
    # (설명, FlowRule JSON, 예상 결과)
    ("정상 FlowRule", {
        "flows": [{"priority": 100, "timeout": 0, "isPermanent": "true",
                   "deviceId": "of:0000000000000001",
                   "treatment": {"instructions": [{"type": "OUTPUT", "port": "2"}]},
                   "selector": {"criteria": [{"type": "ETH_TYPE", "ethType": "0x800"},
                                             {"type": "IPV4_DST", "ip": "10.0.0.1/32"}]}}]
    }, True),

    ("deviceId 형식 오류", {
        "flows": [{"priority": 100, "timeout": 0, "isPermanent": "true",
                   "deviceId": "switch1",  # 오류
                   "treatment": {"instructions": [{"type": "OUTPUT", "port": "2"}]},
                   "selector": {"criteria": [{"type": "ETH_TYPE", "ethType": "0x800"}]}}]
    }, False),

    ("존재하지 않는 criteria type (환각)", {
        "flows": [{"priority": 100, "timeout": 0, "isPermanent": "true",
                   "deviceId": "of:0000000000000001",
                   "treatment": {"instructions": [{"type": "OUTPUT", "port": "2"}]},
                   "selector": {"criteria": [{"type": "DESTINATION_MAC", "mac": "aa:bb:cc:dd:ee:ff"}]}}]  # 환각
    }, False),

    ("존재하지 않는 instruction type (환각)", {
        "flows": [{"priority": 100, "timeout": 0, "isPermanent": "true",
                   "deviceId": "of:0000000000000001",
                   "treatment": {"instructions": [{"type": "FORWARD_TO_PORT", "port": "2"}]},  # 환각
                   "selector": {"criteria": [{"type": "ETH_TYPE", "ethType": "0x800"}]}}]
    }, False),

    ("priority 범위 초과", {
        "flows": [{"priority": 99999, "timeout": 0, "isPermanent": "true",  # 오류
                   "deviceId": "of:0000000000000001",
                   "treatment": {"instructions": [{"type": "OUTPUT", "port": "2"}]},
                   "selector": {"criteria": [{"type": "ETH_TYPE", "ethType": "0x800"}]}}]
    }, False),

    ("selector 없음", {
        "flows": [{"priority": 100, "timeout": 0, "isPermanent": "true",
                   "deviceId": "of:0000000000000001",
                   "treatment": {"instructions": [{"type": "OUTPUT", "port": "2"}]}}]
        # selector 누락
    }, False),

    ("isPermanent 오류", {
        "flows": [{"priority": 100, "timeout": 0, "isPermanent": True,  # bool, 문자열이어야 함
                   "deviceId": "of:0000000000000001",
                   "treatment": {"instructions": [{"type": "OUTPUT", "port": "2"}]},
                   "selector": {"criteria": [{"type": "ETH_TYPE", "ethType": "0x800"}]}}]
    }, False),

    ("정상 DROP 규칙 (treatment 없음)", {
        "flows": [{"priority": 400, "timeout": 0, "isPermanent": "true",
                   "deviceId": "of:0000000000000001",
                   "selector": {"criteria": [{"type": "ETH_TYPE", "ethType": "0x800"},
                                             {"type": "IPV4_SRC", "ip": "10.0.0.1/32"}]}}]
    }, True),

    ("JSON 파싱 불가", "{'priority': 100, invalid json}", False),

    ("criteria 비어있음", {
        "flows": [{"priority": 100, "timeout": 0, "isPermanent": "true",
                   "deviceId": "of:0000000000000001",
                   "treatment": {"instructions": [{"type": "OUTPUT", "port": "2"}]},
                   "selector": {"criteria": []}}]  # 빈 리스트
    }, False),
]


def run_schema_validation_test():
    """Step 1 테스트: 망가진 FlowRule 10개로 탐지율 측정"""
    print("=== Step 1: JSON 스키마 검증 테스트 ===\n")
    results = []

    for desc, flowrule, expected_valid in TEST_CASES:
        result = validate_flowrule(flowrule)
        actual_valid = result["valid"]
        correct = actual_valid == expected_valid

        status = "OK" if correct else "FAIL"
        print(f"[{status}] {desc}")
        if not actual_valid:
            for err in result["errors"]:
                print(f"      오류: {err}")
        results.append({
            "description": desc,
            "expected_valid": expected_valid,
            "actual_valid": actual_valid,
            "correct": correct,
            "errors": result["errors"]
        })

    correct_count = sum(1 for r in results if r["correct"])
    print(f"\n탐지 정확도: {correct_count}/{len(TEST_CASES)} = {correct_count/len(TEST_CASES)*100:.1f}%")
    return results


if __name__ == "__main__":
    run_schema_validation_test()
