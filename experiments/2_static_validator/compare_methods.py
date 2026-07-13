"""
LLM-based vs Rule-based 충돌 탐지 비교 실험
논문 Table용 수치 생성
"""

import os
import sys
import json
import time
import pandas as pd
from sklearn.metrics import classification_report

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASE_DIR, "results")
DATASET_PATH = os.path.join(
    BASE_DIR, "..", "1_netintent_baseline", "NetIntent",
    "GitHub NetIntent", "Datasets", "FlowConflict-ONOS.csv"
)


def load_llm_results():
    """이전에 저장된 LLM-based 결과 로드"""
    import glob
    files = sorted(glob.glob(os.path.join(RESULTS_DIR, "step2_conflict_*.json")))
    if not files:
        return None
    with open(files[-1], encoding="utf-8") as f:
        data = json.load(f)
    print(f"LLM 결과 로드: {files[-1]}")
    return data


def print_comparison_table(llm_result: dict, rule_result: dict):
    """논문용 비교 테이블 출력"""

    def get_metrics(report, label):
        r = report.get(label, {})
        return r.get("precision", 0), r.get("recall", 0), r.get("f1-score", 0)

    llm_r = llm_result["report"]
    rule_r = rule_result["report"]

    print("\n" + "="*70)
    print("논문 Table: LLM-based vs Rule-based 충돌 탐지 비교")
    print("="*70)
    print(f"{'':25s} {'LLM-based':>20s} {'Rule-based':>20s}")
    print("-"*70)

    # Accuracy
    print(f"{'Accuracy (%)':25s} {llm_result['accuracy']:>20.1f} {rule_result['accuracy']:>20.1f}")

    # No (비충돌)
    lp, lr, lf = get_metrics(llm_r, "no")
    rp, rr, rf = get_metrics(rule_r, "no")
    print(f"{'Precision (No)':25s} {lp:>20.3f} {rp:>20.3f}")
    print(f"{'Recall (No)':25s} {lr:>20.3f} {rr:>20.3f}")
    print(f"{'F1 (No)':25s} {lf:>20.3f} {rf:>20.3f}")

    # Yes (충돌)
    lp, lr, lf = get_metrics(llm_r, "yes")
    rp, rr, rf = get_metrics(rule_r, "yes")
    print(f"{'Precision (Yes)':25s} {lp:>20.3f} {rp:>20.3f}")
    print(f"{'Recall (Yes)':25s} {lr:>20.3f} {rr:>20.3f}")
    print(f"{'F1 (Yes)':25s} {lf:>20.3f} {rf:>20.3f}")

    # Macro F1
    lmf = llm_r.get("macro avg", {}).get("f1-score", 0)
    rmf = rule_r.get("macro avg", {}).get("f1-score", 0)
    print(f"{'Macro F1':25s} {lmf:>20.3f} {rmf:>20.3f}")
    print("-"*70)

    # 추가 특성
    print(f"{'API 비용':25s} {'있음 (74회 호출)':>20s} {'없음':>20s}")
    print(f"{'결정성':25s} {'비결정적':>20s} {'결정적':>20s}")
    print(f"{'설명 가능성':25s} {'불투명':>20s} {'완전 투명':>20s}")
    print("="*70)


def save_comparison(llm_result: dict, rule_result: dict):
    """비교 결과 저장"""
    timestamp = int(time.time())
    output = {
        "timestamp": timestamp,
        "llm_based": {
            "accuracy": llm_result["accuracy"],
            "report": llm_result["report"],
            "wrong_count": sum(1 for d in llm_result["details"] if not d["correct"]),
        },
        "rule_based": {
            "accuracy": rule_result["accuracy"],
            "report": rule_result["report"],
            "wrong_count": len(rule_result["wrong_cases"]),
            "wrong_cases": rule_result["wrong_cases"],
        }
    }
    path = os.path.join(RESULTS_DIR, f"comparison_{timestamp}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n비교 결과 저장: {path}")
    return path


def main():
    print("LLM-based vs Rule-based 충돌 탐지 비교\n")

    # Rule-based 실행
    from rule_based_detector import run_rule_based_evaluation
    rule_result = run_rule_based_evaluation()

    # LLM-based 결과 로드 (이미 실행한 결과)
    print("\n" + "="*60)
    llm_data = load_llm_results()
    if llm_data is None:
        print("LLM 결과 파일 없음. conflict_detector.py를 먼저 실행하세요.")
        return

    llm_result = {
        "accuracy": llm_data["accuracy"],
        "report": llm_data["report"],
        "details": llm_data["details"],
    }

    # 비교 테이블 출력
    print_comparison_table(llm_result, rule_result)

    # 결과 저장
    save_comparison(llm_result, rule_result)


if __name__ == "__main__":
    main()
