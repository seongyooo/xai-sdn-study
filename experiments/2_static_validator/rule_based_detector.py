"""
Rule-based 충돌 탐지기 (Static Validator Layer 2)

LLM 없이 순수 조건문으로 FlowRule 충돌 탐지.
FlowConflict-ONOS 74쌍으로 LLM 기반 탐지기와 성능 비교.

충돌 유형 정의:
  Shadowing    : 상위 priority 규칙이 하위 규칙의 match를 완전히 포함 + action 다름
  Redundancy   : match 겹침 + action 같음 (중복 규칙)
  Correlation  : match 겹침 + action 다름 (같은 패킷에 서로 다른 처리)
  Imbrication  : match 부분 포함 (한쪽이 더 구체적) + action 다름
  Generalization: match 포함 관계 + action 같음 (한쪽이 일반화)
"""

import os
import ast
import json
import ipaddress
import pandas as pd
from sklearn.metrics import classification_report

# ── 경로 ───────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(
    BASE_DIR, "..", "1_netintent_baseline", "NetIntent",
    "GitHub NetIntent", "Datasets", "FlowConflict-ONOS.csv"
)


# ── FlowRule 파싱 ───────────────────────────────────────────

def parse_rule(raw) -> dict:
    """CSV에서 읽은 FlowRule 문자열을 단일 flow dict로 변환"""
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except Exception:
            raw = ast.literal_eval(raw)
    # flows 래퍼 처리
    if "flows" in raw:
        return raw["flows"][0]
    return raw


def get_criteria_dict(flow: dict) -> dict:
    """selector.criteria 리스트를 {type: criterion} dict로 변환"""
    criteria = flow.get("selector", {}).get("criteria", [])
    return {c["type"]: c for c in criteria}


def get_action_key(flow: dict) -> str:
    """action을 비교 가능한 문자열로 변환"""
    treatment = flow.get("treatment")
    if treatment is None:
        return "DROP"
    instructions = treatment.get("instructions", [])
    # 순서 무관하게 비교하기 위해 정렬
    return json.dumps(sorted(instructions, key=lambda x: json.dumps(x, sort_keys=True)), sort_keys=True)


def get_priority(flow: dict) -> int:
    return int(flow.get("priority", 0))


# ── IP 범위 비교 ────────────────────────────────────────────

def normalize_hex(val: str) -> str:
    """0x0800 → 0x800 정규화"""
    try:
        return hex(int(val, 16))
    except Exception:
        return val.lower()


def ip_overlaps(ip1: str, ip2: str) -> bool:
    """두 IP CIDR 범위가 겹치는지 확인"""
    try:
        n1 = ipaddress.ip_network(ip1, strict=False)
        n2 = ipaddress.ip_network(ip2, strict=False)
        return n1.overlaps(n2)
    except Exception:
        return ip1 == ip2


def ip_is_subset(ip_sub: str, ip_super: str) -> bool:
    """ip_sub이 ip_super에 완전히 포함되는지 확인 (subnet_of)"""
    try:
        n_sub = ipaddress.ip_network(ip_sub, strict=False)
        n_super = ipaddress.ip_network(ip_super, strict=False)
        return n_sub.subnet_of(n_super)
    except Exception:
        return ip_sub == ip_super


# ── Match 비교 ──────────────────────────────────────────────

def _field_value(c: dict, ctype: str):
    """criterion에서 비교 가능한 값 추출"""
    if ctype == "ETH_TYPE":
        return normalize_hex(c.get("ethType", ""))
    elif ctype in ("IPV4_SRC", "IPV4_DST"):
        return c.get("ip", "")
    elif ctype == "IP_PROTO":
        return str(c.get("protocol", ""))
    elif ctype == "TCP_DST":
        return str(c.get("tcpPort", ""))
    elif ctype == "UDP_DST":
        # 데이터셋에 UDP_DST인데 tcpPort 키를 쓰는 경우가 있음 (데이터 오류 방어)
        return str(c.get("udpPort", "") or c.get("tcpPort", ""))
    elif ctype == "TCP_SRC":
        return str(c.get("tcpPort", ""))
    elif ctype == "UDP_SRC":
        return str(c.get("udpPort", "") or c.get("tcpPort", ""))
    elif ctype == "IN_PORT":
        return str(c.get("port", ""))
    elif ctype == "VLAN_VID":
        return str(c.get("vlanId", ""))
    return json.dumps(c, sort_keys=True)


def criteria_overlap(c1: dict, c2: dict) -> bool:
    """
    두 criteria dict가 같은 패킷을 매치할 수 있는지 확인.
    모든 공통 필드에서 충돌이 없어야 overlap.
    """
    common_types = set(c1.keys()) & set(c2.keys())

    # 공통 필드가 없는 경우: ETH_TYPE 기반 의미적 호환성 체크
    # 공통 필드가 없다고 무조건 overlap=True로 반환하면 False Positive 발생.
    # 예) ARP 규칙(ETH_TYPE=0x806)과 IPV4_SRC 규칙은 같은 패킷을 절대 매치 못함.
    if not common_types:
        ip_fields = {"IPV4_SRC", "IPV4_DST", "IP_PROTO", "TCP_SRC", "TCP_DST", "UDP_SRC", "UDP_DST"}
        eth_c1 = _field_value(c1["ETH_TYPE"], "ETH_TYPE") if "ETH_TYPE" in c1 else None
        eth_c2 = _field_value(c2["ETH_TYPE"], "ETH_TYPE") if "ETH_TYPE" in c2 else None
        # ARP(0x806) 규칙은 IP 레벨 필드와 겹칠 수 없음
        if eth_c1 == "0x806" and ip_fields & set(c2.keys()):
            return False
        if eth_c2 == "0x806" and ip_fields & set(c1.keys()):
            return False
        # IPv6(0x86dd) 규칙은 IPv4 주소 필드와 겹칠 수 없음
        if eth_c1 == "0x86dd" and ip_fields & set(c2.keys()):
            return False
        if eth_c2 == "0x86dd" and ip_fields & set(c1.keys()):
            return False
        return True

    for ctype in common_types:
        v1 = c1[ctype]
        v2 = c2[ctype]

        if ctype in ("IPV4_SRC", "IPV4_DST"):
            if not ip_overlaps(_field_value(v1, ctype), _field_value(v2, ctype)):
                return False
        else:
            if _field_value(v1, ctype) != _field_value(v2, ctype):
                return False

    return True  # 모든 공통 필드에서 충돌 없음 → overlap


def criteria_equal(c1: dict, c2: dict) -> bool:
    """두 criteria dict가 동일한 match인지 확인"""
    if set(c1.keys()) != set(c2.keys()):
        return False
    for ctype in c1:
        v1 = c1[ctype]
        v2 = c2[ctype]
        if ctype in ("IPV4_SRC", "IPV4_DST"):
            ip1 = _field_value(v1, ctype)
            ip2 = _field_value(v2, ctype)
            if ip1 != ip2:
                return False
        else:
            if _field_value(v1, ctype) != _field_value(v2, ctype):
                return False
    return True


def is_subset(c_sub: dict, c_super: dict) -> bool:
    """
    c_sub의 match가 c_super의 match에 완전히 포함되는지 확인.
    c_super에 없는 필드가 c_sub에 있으면 c_sub이 더 구체적 → subset.
    c_sub에 없는 필드가 c_super에 있으면 c_super가 더 구체적 → not subset.
    """
    # c_super에 없는 필드가 c_sub에 있으면 c_sub이 더 좁음 (subset 가능)
    for ctype in c_super:
        if ctype not in c_sub:
            return False  # c_super가 더 구체적 → c_sub은 subset 아님

    for ctype in c_sub:
        if ctype not in c_super:
            continue  # c_sub이 더 구체적인 필드 → subset 조건 충족

        v_sub = c_sub[ctype]
        v_super = c_super[ctype]

        if ctype in ("IPV4_SRC", "IPV4_DST"):
            if not ip_is_subset(_field_value(v_sub, ctype), _field_value(v_super, ctype)):
                return False
        else:
            if _field_value(v_sub, ctype) != _field_value(v_super, ctype):
                return False

    return True


# ── 충돌 탐지 핵심 로직 ─────────────────────────────────────

def detect_conflict_rule_based(rule1_raw, rule2_raw) -> dict:
    """
    순수 규칙 기반으로 두 FlowRule의 충돌 탐지.

    Returns:
        {
          "conflicting": bool,
          "conflict_type": str | None,
          "reason": str
        }
    """
    try:
        f1 = parse_rule(rule1_raw)
        f2 = parse_rule(rule2_raw)
    except Exception as e:
        return {"conflicting": False, "conflict_type": None, "reason": f"파싱 오류: {e}"}

    c1 = get_criteria_dict(f1)
    c2 = get_criteria_dict(f2)
    p1 = get_priority(f1)
    p2 = get_priority(f2)
    a1 = get_action_key(f1)
    a2 = get_action_key(f2)

    # ── 1단계: match overlap 확인 ──────────────────────────
    if not criteria_overlap(c1, c2):
        return {
            "conflicting": False,
            "conflict_type": None,
            "reason": "match 기준이 겹치지 않아 충돌 없음"
        }

    # overlap 있음 → 충돌 유형 분류
    tcp_udp_note = ""

    # ── 2단계: match 완전 동일 여부 ───────────────────────
    match_equal = criteria_equal(c1, c2)
    action_equal = (a1 == a2)

    # Redundancy: match 동일 + action 동일 (완전 중복)
    if match_equal and action_equal:
        return {
            "conflicting": True,
            "conflict_type": "Redundancy",
            "reason": f"match와 action이 완전히 동일한 중복 규칙 (priority {p1} vs {p2})"
        }

    # ── 3단계: 포함 관계 확인 ─────────────────────────────
    c1_sub_c2 = is_subset(c1, c2)  # c1이 c2의 부분집합
    c2_sub_c1 = is_subset(c2, c1)  # c2가 c1의 부분집합

    # Shadowing: 상위 priority가 하위를 완전히 포함 + action 다름
    if p1 != p2 and not action_equal:
        high_c, low_c = (c1, c2) if p1 > p2 else (c2, c1)
        high_p, low_p = max(p1, p2), min(p1, p2)

        # 상위 priority가 하위를 포함하면 Shadowing
        if is_subset(low_c, high_c):
            return {
                "conflicting": True,
                "conflict_type": "Shadowing",
                "reason": f"priority {high_p}이 priority {low_p}의 match를 완전히 포함하여 하위 규칙이 도달 불가"
            }

    if not action_equal and (c1_sub_c2 or c2_sub_c1):
        return {
            "conflicting": True,
            "conflict_type": "Imbrication",
            "reason": f"한 규칙이 다른 규칙의 match 부분집합 (더 구체적인 규칙이 일반 규칙과 겹침){tcp_udp_note}"
        }

    if action_equal and (c1_sub_c2 or c2_sub_c1):
        return {
            "conflicting": True,
            "conflict_type": "Generalization",
            "reason": f"한 규칙이 다른 규칙의 일반화 버전 (더 넓은 match, 같은 action)"
        }

    # Correlation: match 겹침 + action 다름 (나머지)
    if not action_equal:
        return {
            "conflicting": True,
            "conflict_type": "Correlation",
            "reason": f"match가 겹치지만 서로 다른 action 수행 (priority {p1} vs {p2}){tcp_udp_note}"
        }

    # match 겹침 + action 동일 + match 다름 → 잠재적 Redundancy
    return {
        "conflicting": True,
        "conflict_type": "Redundancy",
        "reason": "match가 부분적으로 겹치고 action이 동일 (잠재적 중복)"
    }


# ── 평가 ───────────────────────────────────────────────────

def run_rule_based_evaluation():
    """FlowConflict-ONOS 74쌍으로 Rule-based 탐지기 평가"""
    print("=== Rule-based 충돌 탐지기 평가 (74쌍) ===\n")

    df = pd.read_csv(DATASET_PATH)
    df["Conflicting_norm"] = df["Conflicting"].str.strip().str.lower()

    y_true, y_pred = [], []
    details = []
    wrong_cases = []

    for idx, row in df.iterrows():
        true_label = row["Conflicting_norm"]
        true_type = str(row.get("Type of Conflict", ""))

        result = detect_conflict_rule_based(
            row["ONOS Flow Rule 1"],
            row["ONOS Flow Rule 2"]
        )

        pred_label = "yes" if result["conflicting"] else "no"
        pred_type = result["conflict_type"]
        correct = pred_label == true_label

        y_true.append(true_label)
        y_pred.append(pred_label)

        status = "OK" if correct else "FAIL"
        print(f"  [{status}] Row {idx+1:2d} | 정답:{true_label:3s} 예측:{pred_label:3s} | {true_type:15s} → {str(pred_type):15s} | {result['reason'][:50]}")

        detail = {
            "row": int(idx),
            "true_conflicting": true_label,
            "true_type": true_type,
            "pred_conflicting": pred_label,
            "pred_type": pred_type,
            "reason": result["reason"],
            "correct": correct,
        }
        details.append(detail)
        if not correct:
            wrong_cases.append(detail)

    # ── 결과 출력 ─────────────────────────────────────────
    accuracy = sum(1 for a, b in zip(y_true, y_pred) if a == b) / len(y_true) * 100

    print("\n" + "="*60)
    print("분류 성능 (Rule-based)")
    print("="*60)
    print(classification_report(y_true, y_pred, target_names=["no", "yes"]))
    print(f"Accuracy: {accuracy:.1f}%")

    if wrong_cases:
        print(f"\n틀린 케이스 {len(wrong_cases)}개:")
        for w in wrong_cases:
            print(f"  Row {w['row']+1}: 정답={w['true_conflicting']} 예측={w['pred_conflicting']} | 실제유형={w['true_type']}")
            print(f"    판단 이유: {w['reason']}")

    report = classification_report(y_true, y_pred, target_names=["no", "yes"], output_dict=True)
    return {
        "method": "rule_based",
        "accuracy": round(accuracy, 1),
        "y_true": y_true,
        "y_pred": y_pred,
        "report": report,
        "details": details,
        "wrong_cases": wrong_cases,
    }


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    result = run_rule_based_evaluation()
