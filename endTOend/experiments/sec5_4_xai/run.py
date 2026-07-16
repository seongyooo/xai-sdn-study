"""
sec5_4_xai/run.py — 논문 Section 5.4: XAI 설명 충실도 자동 평가

각 XAI evidence 항목이 실제 stage 출력과 연결되어 있는지 자동 검사한다.

충실도 기준:
  E1. ir_summary에 action 필드가 포함되어 있는가
  E2. flowrule_summary에 deviceId와 priority가 포함되어 있는가
  E3. static_summary가 StaticResult.summary()와 동일한가
  E4. twin_summary가 twin_result.status를 반영하는가
  E5. decision이 static.passed + twin.status 조합과 일치하는가
  E6. evidence 배열이 4개 스테이지를 모두 포함하는가

실행:
    cd endTOend/
    python experiments/sec5_4_xai/run.py
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

_BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_BASE))

from models.intent_ir import IntentIR
from stage3_static.static_validator import StaticResult
from stage4_twin.twin_verifier import TwinResult
from stage5_xai.explainer import XAIExplainer

TEST_CASES = [
    # (id, ir_kwargs, static_passed, twin_status, expected_decision)
    ("X01", dict(action="block",   device_hint="s1", src_ip="10.0.0.1", dst_ip="10.0.0.4"), True,  "passed",  "APPROVE"),
    ("X02", dict(action="forward", device_hint="s1", dst_ip="10.0.0.3", out_port=2),        True,  "passed",  "APPROVE"),
    ("X03", dict(action="block",   device_hint="s4", src_ip="10.0.0.1"),                    False, "passed",  "REJECT"),
    ("X04", dict(action="forward", device_hint="s1", ip_proto="tcp", dst_port=80),          True,  "failed",  "REJECT"),
    ("X05", dict(action="block",   device_hint="s1", src_ip="10.0.0.3"),                    True,  "skipped", "APPROVE_WITHOUT_TWIN"),
    ("X06", dict(action="qos",     device_hint="s1", dst_ip="10.0.0.3", queue_id=0),        True,  "skipped", "APPROVE_WITHOUT_TWIN"),
]

STAGE_LABELS = ["Stage1_IntentParsing", "Stage2_FlowRuleCompile",
                "Stage3_StaticValidation", "Stage4_DigitalTwin"]


def check_faithfulness(report, ir, static_result, twin_result) -> dict[str, bool]:
    checks = {}

    # E1: ir_summary에 action 포함
    checks["E1_ir_has_action"] = ir.action in report.ir_summary

    # E2: flowrule_summary에 deviceId, priority 포함
    checks["E2_fr_has_device_priority"] = (
        "deviceId=" in report.flowrule_summary and
        "priority=" in report.flowrule_summary
    )

    # E3: static_summary가 StaticResult.summary()와 동일
    checks["E3_static_summary_match"] = (
        report.static_summary == static_result.summary()
    )

    # E4: twin_summary가 status를 반영
    status_keywords = {
        "passed": "통과",
        "failed": "실패",
        "skipped": "스킵",
        "error": "오류",
    }
    keyword = status_keywords.get(twin_result.status, twin_result.status)
    checks["E4_twin_summary_reflects_status"] = keyword in report.twin_summary

    # E5: decision이 올바른가
    if not static_result.passed or twin_result.status in ("failed", "error"):
        expected_decision = "REJECT"
    elif twin_result.status == "skipped":
        expected_decision = "APPROVE_WITHOUT_TWIN"
    else:
        expected_decision = "APPROVE"
    checks["E5_decision_correct"] = (report.decision == expected_decision)

    # E6: evidence가 4개 스테이지 모두 포함
    evidence_stages = {e["stage"] for e in report.evidence}
    checks["E6_evidence_all_stages"] = all(s in evidence_stages for s in STAGE_LABELS)

    return checks


def main():
    from stage2_flowrule.compiler import compile_flowrule

    explainer = XAIExplainer()
    rows = []
    all_checks = {k: [] for k in [
        "E1_ir_has_action", "E2_fr_has_device_priority", "E3_static_summary_match",
        "E4_twin_summary_reflects_status", "E5_decision_correct", "E6_evidence_all_stages"
    ]}

    print("Section 5.4 — XAI 설명 충실도")
    print("=" * 60)

    for case_id, ir_kwargs, static_passed, twin_status, expected_decision in TEST_CASES:
        ir = IntentIR(**ir_kwargs)
        flowrule = compile_flowrule(ir)

        schema_errors = [] if static_passed else ["mock schema error"]
        static_result = StaticResult(passed=static_passed, schema_errors=schema_errors)
        twin_result = TwinResult(
            status=twin_status,
            reason="테스트" if twin_status == "skipped" else None,
            checks={"intent_check": twin_status == "passed"},
        )

        report = explainer.explain("test intent", ir, flowrule, static_result, twin_result)
        checks = check_faithfulness(report, ir, static_result, twin_result)

        n_pass = sum(checks.values())
        n_total = len(checks)
        decision_ok = "✅" if report.decision == expected_decision else "❌"

        print(f"\n[{case_id}] action={ir.action} static={'OK' if static_passed else 'FAIL'} twin={twin_status}")
        print(f"  decision: {report.decision} (expected {expected_decision}) {decision_ok}")
        print(f"  faithfulness: {n_pass}/{n_total}")
        for k, v in checks.items():
            print(f"    {'✅' if v else '❌'} {k}")

        row = {"id": case_id, "expected_decision": expected_decision, "actual_decision": report.decision}
        for k, v in checks.items():
            row[k] = "1" if v else "0"
            all_checks[k].append(v)
        row["faithfulness_score"] = f"{n_pass}/{n_total}"
        rows.append(row)

    print("\n" + "=" * 60)
    print("  충실도 체크별 통과율")
    for k, vals in all_checks.items():
        pct = 100 * sum(vals) / len(vals) if vals else 0
        print(f"  {k}: {sum(vals)}/{len(vals)} ({pct:.0f}%)")
    overall = sum(v for vals in all_checks.values() for v in vals)
    total = sum(len(vals) for vals in all_checks.values())
    print(f"  overall: {overall}/{total} ({100*overall/total:.1f}%)")
    print("=" * 60)

    out = Path(__file__).parent / "results" / "xai_faithfulness.csv"
    out.parent.mkdir(exist_ok=True)
    fieldnames = ["id", "expected_decision", "actual_decision"] + list(all_checks.keys()) + ["faithfulness_score"]
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"결과 저장: {out}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
