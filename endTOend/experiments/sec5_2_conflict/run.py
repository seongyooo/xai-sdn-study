"""
sec5_2_conflict/run.py — 논문 Section 5.2: 정적 검증 충돌 탐지율

각 충돌 유형(Shadowing / Redundancy / Correlation / Imbrication / Generalization)에 대해
탐지 정밀도(precision) / 재현율(recall)을 측정한다.

테스트셋: 이 파일 내 CONFLICT_CASES (수작업 레이블)
결과: results/conflict_detection.csv

실행:
    cd endTOend/
    python experiments/sec5_2_conflict/run.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

_BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_BASE))

from stage3_static.conflict_detector import detect_conflict

# ── 테스트 케이스 정의 ────────────────────────────────────────────
# 각 케이스: (id, new_flow, existing_flow, expected_conflict_type)
# expected_conflict_type = None → 충돌 없음이 정답

def _flow(priority, action, src_ip=None, dst_ip=None, proto=None, dst_port=None,
          in_port=None, out_port=None, queue_id=None, device="of:0000000000000001"):
    criteria = [{"type": "ETH_TYPE", "ethType": "0x800"}]
    if src_ip:
        criteria.append({"type": "IPV4_SRC", "ip": src_ip})
    if dst_ip:
        criteria.append({"type": "IPV4_DST", "ip": dst_ip})
    if proto == "tcp":
        criteria.append({"type": "IP_PROTO", "protocol": 6})
    elif proto == "udp":
        criteria.append({"type": "IP_PROTO", "protocol": 17})
    if dst_port:
        criteria.append({"type": "TCP_DST", "tcpPort": dst_port})
    if in_port:
        criteria.append({"type": "IN_PORT", "port": in_port})

    treatment = None
    if action == "forward":
        instructions = [{"type": "OUTPUT", "port": str(out_port or "NORMAL")}]
        if queue_id is not None:
            instructions.append({"type": "QUEUE", "queueId": queue_id})
        treatment = {"instructions": instructions}
    elif action == "block":
        treatment = {"instructions": [{"type": "NOACTION"}]}

    flow = {
        "priority": priority,
        "deviceId": device,
        "selector": {"criteria": criteria},
    }
    if treatment:
        flow["treatment"] = treatment
    return flow


CONFLICT_CASES = [
    # ── Shadowing: 새 고우선순위가 기존 저우선순위를 완전 포함 ────
    ("S01", "Shadowing",
     _flow(50000, "block", src_ip="10.0.0.1/32", dst_ip="10.0.0.4/32"),
     _flow(100,   "forward", src_ip="10.0.0.1/32", dst_ip="10.0.0.4/32")),

    ("S02", "Shadowing",
     _flow(60000, "block", dst_ip="10.0.0.0/24"),
     _flow(1000,  "forward", dst_ip="10.0.0.1/32")),

    # ── Redundancy: match 동일 + action 동일 ────────────────────
    ("R01", "Redundancy",
     _flow(50000, "block", src_ip="10.0.0.1/32", dst_ip="10.0.0.4/32"),
     _flow(50000, "block", src_ip="10.0.0.1/32", dst_ip="10.0.0.4/32")),

    ("R02", "Redundancy",
     _flow(32768, "forward", dst_ip="10.0.0.3/32", proto="tcp", dst_port=80, out_port=2),
     _flow(32768, "forward", dst_ip="10.0.0.3/32", proto="tcp", dst_port=80, out_port=2)),

    # ── Imbrication: 동일 priority + 포함 관계 + action 다름 ────
    ("I01", "Imbrication",
     _flow(50000, "block", dst_ip="10.0.0.1/32"),
     _flow(50000, "forward", dst_ip="10.0.0.0/24")),

    ("I02", "Imbrication",
     _flow(50000, "block", src_ip="10.0.0.1/32", proto="tcp"),
     _flow(50000, "forward", src_ip="10.0.0.1/32")),

    # ── Correlation: 동일 priority + 겹침 + action 다름 ─────────
    ("C01", "Correlation",
     _flow(50000, "block", src_ip="10.0.0.0/24"),
     _flow(50000, "forward", dst_ip="10.0.0.0/24")),

    # ── Generalization: 포함 관계 + action 동일 ─────────────────
    ("G01", "Generalization",
     _flow(50000, "forward", dst_ip="10.0.0.0/24", out_port=2),
     _flow(50000, "forward", dst_ip="10.0.0.1/32", out_port=2)),

    # ── 충돌 없음: 우선순위로 해소 ──────────────────────────────
    ("N01", None,   # 새 룰 p_new > p_existing → override, 충돌 아님
     _flow(50000, "block", src_ip="10.0.0.1/32"),
     _flow(10,    "forward")),

    ("N02", None,   # match 비겹침
     _flow(50000, "block", src_ip="10.0.0.1/32"),
     _flow(50000, "forward", src_ip="10.0.0.2/32")),

    ("N03", None,   # proto 다름 → 패킷 겹치지 않음
     _flow(50000, "block", proto="tcp", dst_port=80),
     _flow(50000, "forward", proto="udp")),
]


def main():
    rows = []
    tp = fp = tn = fn = 0

    for case_id, expected_type, new_flow, existing_flow in CONFLICT_CASES:
        result = detect_conflict({"flows": [new_flow]}, [existing_flow])

        if result:
            detected_type = result[0]["conflict_type"]
            detected = True
        else:
            detected_type = None
            detected = False

        expected_conflict = expected_type is not None

        if expected_conflict and detected:
            outcome = "TP" if detected_type == expected_type else "FP_wrong_type"
        elif expected_conflict and not detected:
            outcome = "FN"
        elif not expected_conflict and detected:
            outcome = "FP"
        else:
            outcome = "TN"

        if outcome == "TP":
            tp += 1
        elif outcome in ("FP", "FP_wrong_type"):
            fp += 1
        elif outcome == "FN":
            fn += 1
        else:
            tn += 1

        rows.append({
            "id": case_id,
            "expected_type": expected_type or "none",
            "detected_type": detected_type or "none",
            "outcome": outcome,
        })
        status = "✅" if outcome in ("TP", "TN") else "❌"
        print(f"[{status}] {case_id}: expected={expected_type or 'none'} detected={detected_type or 'none'} → {outcome}")

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1        = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    print("\n" + "=" * 50)
    print(f"  TP={tp}  FP={fp}  FN={fn}  TN={tn}")
    print(f"  Precision : {precision:.3f}")
    print(f"  Recall    : {recall:.3f}")
    print(f"  F1        : {f1:.3f}")
    print("=" * 50)

    out = Path(__file__).parent / "results" / "conflict_detection.csv"
    out.parent.mkdir(exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "expected_type", "detected_type", "outcome"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"결과 저장: {out}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
