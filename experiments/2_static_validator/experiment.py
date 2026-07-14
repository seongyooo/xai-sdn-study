"""
실험 2 — Static Validator 전체 실행 엔트리포인트
Step 1: JSON 스키마 검증
Step 2: 충돌 탐지
Step 3: 충돌 이유 설명
"""

import os
import sys
import json
import time
import ast
import argparse
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
RESULTS_DIR = os.path.join(BASE_DIR, "results")
DATASET_PATH = os.path.join(
    BASE_DIR, "..", "netintent_baseline", "NetIntent",
    "GitHub NetIntent", "Datasets", "FlowConflict-ONOS.csv"
)
os.makedirs(RESULTS_DIR, exist_ok=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default=os.environ.get("LLM_MODEL", "qwen3:8b"),
                        help="LLM model name (e.g. qwen3:8b, gemma4:e4b)")
    args = parser.parse_args()
    os.environ["LLM_MODEL"] = args.model
    print(f"[Model: {args.model}]")

    run_steps = os.environ.get("RUN_STEPS", "1,2,3")
    steps = [s.strip() for s in run_steps.split(",")]
    # 빠른 테스트용: SAMPLE_SIZE 환경변수로 개수 제한 가능
    sample_size = int(os.environ.get("SAMPLE_SIZE", "0")) or None

    all_results = {}
    model_tag = args.model.replace(":", "-")
    timestamp = int(time.time())

    # ── Step 1: 스키마 검증 ──────────────────────────────────
    if "1" in steps:
        from validator import run_schema_validation_test
        print("\n" + "="*60)
        results_1 = run_schema_validation_test()
        all_results["schema_validation"] = results_1

        path = os.path.join(RESULTS_DIR, f"step1_schema_{model_tag}_{timestamp}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(results_1, f, ensure_ascii=False, indent=2)
        print(f"\n결과 저장: {path}")

    # ── Step 2: 충돌 탐지 ───────────────────────────────────
    if "2" in steps:
        from conflict_detector import run_conflict_detection
        print("\n" + "="*60)
        results_2 = run_conflict_detection(sample_size=sample_size)
        all_results["conflict_detection"] = {
            "accuracy": results_2["accuracy"],
            "report": results_2["report"],
            "details": results_2["details"],
        }

        path = os.path.join(RESULTS_DIR, f"step2_conflict_{model_tag}_{timestamp}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(all_results["conflict_detection"], f, ensure_ascii=False, indent=2)
        print(f"\n결과 저장: {path}")

    # ── Step 3: 충돌 설명 ───────────────────────────────────
    if "3" in steps:
        from explainer import run_explanation_demo

        # Step 2 결과에서 충돌 케이스 추출 (또는 데이터셋에서 직접)
        df = pd.read_csv(DATASET_PATH)
        df_conflict = df[df["Conflicting"].str.lower() == "yes"].dropna(subset=["Type of Conflict"])

        demo_cases = []
        seen_types = set()
        for _, row in df_conflict.iterrows():
            ctype = row["Type of Conflict"]
            if ctype in seen_types:
                continue
            try:
                rule1 = ast.literal_eval(str(row["ONOS Flow Rule 1"]))
                rule2 = ast.literal_eval(str(row["ONOS Flow Rule 2"]))
                demo_cases.append({"rule1": rule1, "rule2": rule2, "conflict_type": ctype})
                seen_types.add(ctype)
            except Exception:
                continue

        print("\n" + "="*60)
        results_3 = run_explanation_demo(demo_cases)
        all_results["conflict_explanation"] = results_3

        path = os.path.join(RESULTS_DIR, f"step3_explanation_{model_tag}_{timestamp}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(results_3, f, ensure_ascii=False, indent=2)
        print(f"\n결과 저장: {path}")

    # ── 최종 요약 ────────────────────────────────────────────
    print("\n" + "="*60)
    print("실험 2 완료 요약")
    print("="*60)

    if "schema_validation" in all_results:
        correct = sum(1 for r in all_results["schema_validation"] if r["correct"])
        total = len(all_results["schema_validation"])
        print(f"Step 1 (스키마 검증): {correct}/{total} = {correct/total*100:.1f}%")

    if "conflict_detection" in all_results:
        print(f"Step 2 (충돌 탐지): Accuracy {all_results['conflict_detection']['accuracy']}%")

    if "conflict_explanation" in all_results:
        print(f"Step 3 (충돌 설명): {len(all_results['conflict_explanation'])}개 케이스 설명 생성 완료")


if __name__ == "__main__":
    main()
