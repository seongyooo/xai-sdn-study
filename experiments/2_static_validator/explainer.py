"""
Step 3: 충돌 이유 자연어 설명 생성 (우리 차별점)
NetIntent는 충돌 탐지만 함 → 우리는 왜 충돌하는지 설명까지 추가
"""

import os
import json
import time
from google import genai
from google.genai import types

client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
MODEL = "gemini-3.1-flash-lite"

EXPLANATION_PROMPT = """You are an SDN network expert explaining FlowRule conflicts to network operators.

Given two conflicting ONOS FlowRules and their conflict type, generate a clear natural language explanation that:
1. Describes WHY the conflict occurs (specific fields causing the conflict)
2. Explains the IMPACT (what happens in the network due to this conflict)
3. Suggests a REMEDY (how to fix it)

Write in plain language that a network operator can understand.
Keep the explanation concise (3-5 sentences per section).

Respond in JSON format:
{
  "why": "explanation of why the conflict occurs",
  "impact": "explanation of the network impact",
  "remedy": "suggested fix"
}"""


def explain_conflict(rule1: dict, rule2: dict, conflict_type: str, max_retries: int = 3) -> dict:
    """충돌하는 두 FlowRule에 대한 자연어 설명 생성"""
    prompt = f"""Conflict Type: {conflict_type}

FlowRule 1:
{json.dumps(rule1, indent=2)}

FlowRule 2:
{json.dumps(rule2, indent=2)}

Explain this conflict in detail."""

    for attempt in range(max_retries):
        try:
            time.sleep(2)
            resp = client.models.generate_content(
                model=MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=EXPLANATION_PROMPT,
                    temperature=0.3,
                    response_mime_type="application/json",
                ),
            )
            return json.loads(resp.text)
        except Exception as e:
            err = str(e)
            print(f"  [attempt {attempt+1}] Error: {err[:80]}")
            if "429" in err:
                wait = 15 * (attempt + 1)
                time.sleep(wait)
            else:
                time.sleep(2)

    return {"why": "설명 생성 실패", "impact": "", "remedy": ""}


def format_conflict_report(rule1: dict, rule2: dict, conflict_type: str, explanation: dict) -> str:
    """충돌 탐지 보고서 포맷팅"""
    lines = [
        "=" * 60,
        "[충돌 탐지 보고서]",
        "=" * 60,
        f"충돌 유형: {conflict_type}",
        "",
        "[ 왜 충돌하는가 ]",
        explanation.get("why", ""),
        "",
        "[ 네트워크 영향 ]",
        explanation.get("impact", ""),
        "",
        "[ 권장 조치 ]",
        explanation.get("remedy", ""),
        "=" * 60,
    ]
    return "\n".join(lines)


def run_explanation_demo(conflict_cases: list):
    """
    충돌 케이스에 대한 설명 생성 데모

    Args:
        conflict_cases: [{"rule1": dict, "rule2": dict, "conflict_type": str}, ...]
    """
    print("=== Step 3: 충돌 이유 설명 생성 ===\n")
    results = []

    for i, case in enumerate(conflict_cases):
        rule1 = case["rule1"]
        rule2 = case["rule2"]
        conflict_type = case["conflict_type"]

        print(f"[{i+1}/{len(conflict_cases)}] {conflict_type} 충돌 설명 생성 중...")

        explanation = explain_conflict(rule1, rule2, conflict_type)
        report = format_conflict_report(rule1, rule2, conflict_type, explanation)

        print(report)
        print()

        results.append({
            "conflict_type": conflict_type,
            "explanation": explanation,
            "report": report,
        })

    return results


if __name__ == "__main__":
    # 데모: 충돌 유형별 예시 1개씩
    import ast
    import pandas as pd

    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATASET_PATH = os.path.join(
        BASE_DIR, "..", "netintent_baseline", "NetIntent",
        "GitHub NetIntent", "Datasets", "FlowConflict-ONOS.csv"
    )

    df = pd.read_csv(DATASET_PATH)
    df_conflict = df[df["Conflicting"].str.lower() == "yes"].dropna(subset=["Type of Conflict"])

    # 충돌 유형별 첫 번째 케이스만
    demo_cases = []
    for conflict_type in df_conflict["Type of Conflict"].unique():
        row = df_conflict[df_conflict["Type of Conflict"] == conflict_type].iloc[0]
        try:
            rule1 = ast.literal_eval(str(row["ONOS Flow Rule 1"]))
            rule2 = ast.literal_eval(str(row["ONOS Flow Rule 2"]))
            demo_cases.append({"rule1": rule1, "rule2": rule2, "conflict_type": conflict_type})
        except Exception:
            continue

    run_explanation_demo(demo_cases)
