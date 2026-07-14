"""
Step 3: 충돌 이유 자연어 설명 생성 (우리 차별점)
NetIntent는 충돌 탐지만 함 → 우리는 왜 충돌하는지 설명까지 추가
"""

import os
import json
import time
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# ── LLM (Ollama public endpoint) ────────────────────────────
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://ollama.jangmyun.dev/v1")
LLM_MODEL    = os.environ.get("LLM_MODEL", "qwen3:8b")
LLM_HEADERS  = {"Content-Type": "application/json", "Authorization": f"Bearer {os.environ.get('LLM_API_KEY', 'ollama')}"}

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
            resp = requests.post(
                f"{LLM_BASE_URL}/chat/completions",
                headers=LLM_HEADERS,
                json={
                    "model": LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": EXPLANATION_PROMPT},
                        {"role": "user",   "content": prompt},
                    ],
                    "temperature": 0.3,
                    "stream": True,
                    "response_format": {"type": "json_object"},
                },
                timeout=300,
                stream=True,
            )
            resp.raise_for_status()
            content = ""
            for line in resp.iter_lines():
                if not line:
                    continue
                line = line.decode("utf-8") if isinstance(line, bytes) else line
                if line.startswith("data: "):
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        break
                    chunk = json.loads(data)
                    content += chunk["choices"][0]["delta"].get("content", "")
            return json.loads(content)
        except Exception as e:
            err = str(e)
            print(f"  [attempt {attempt+1}] Error: {err[:80]}")
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
