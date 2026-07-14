"""
Step 2: 충돌 탐지
FlowConflict-ONOS 데이터셋 (74쌍)으로 LLM 기반 충돌 탐지 평가
"""

import os
import ast
import json
import time
import requests
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from sklearn.metrics import classification_report, confusion_matrix

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

# ── 경로 설정 ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(
    BASE_DIR, "..", "netintent_baseline", "NetIntent",
    "GitHub NetIntent", "Datasets", "FlowConflict-ONOS.csv"
)

# ── LLM (Ollama public endpoint) ────────────────────────────
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "https://ollama.jangmyun.dev/v1")
LLM_MODEL    = os.environ.get("LLM_MODEL", "qwen3:8b")
LLM_HEADERS  = {"Content-Type": "application/json", "Authorization": f"Bearer {os.environ.get('LLM_API_KEY', 'ollama')}"}

# ── 프롬프트 ───────────────────────────────────────────────
CONFLICT_DETECTION_PROMPT = """You are an expert in SDN (Software-Defined Networking) and ONOS controller flow rules.

Your task is to analyze two ONOS FlowRule JSONs and determine if they conflict.

## Conflict Types
- **Shadowing**: A higher-priority rule completely covers a lower-priority rule with the same or broader match criteria, making the lower-priority rule unreachable.
- **Redundancy**: Two rules have identical match criteria and actions (duplicates).
- **Correlation**: Two rules match overlapping traffic but apply different actions (e.g., one forwards, one drops).
- **Imbrication**: Two rules partially overlap in their match criteria (subset/superset relationship).
- **Generalization**: One rule is a generalization of another (broader match, same action).

## Response Format (JSON only)
{
  "conflicting": true or false,
  "conflict_type": "Shadowing" | "Redundancy" | "Correlation" | "Imbrication" | "Generalization" | null,
  "reason": "one sentence explanation"
}

Respond in JSON only. No other text."""


def parse_flowrule(raw):
    """CSV에서 읽은 FlowRule 문자열을 dict로 변환"""
    if isinstance(raw, dict):
        return raw
    try:
        return json.loads(raw)
    except Exception:
        try:
            return ast.literal_eval(raw)
        except Exception:
            return None


def normalize_label(label: str) -> str:
    """Yes/yes → yes 정규화"""
    return str(label).strip().lower()


def detect_conflict(rule1: dict, rule2: dict, max_retries: int = 3) -> dict:
    """LLM으로 두 FlowRule의 충돌 여부 판단"""
    prompt = f"""FlowRule 1:
{json.dumps(rule1, indent=2)}

FlowRule 2:
{json.dumps(rule2, indent=2)}

Analyze if these two ONOS FlowRules conflict."""

    for attempt in range(max_retries):
        try:
            resp = requests.post(
                f"{LLM_BASE_URL}/chat/completions",
                headers=LLM_HEADERS,
                json={
                    "model": LLM_MODEL,
                    "messages": [
                        {"role": "system", "content": CONFLICT_DETECTION_PROMPT},
                        {"role": "user",   "content": prompt},
                    ],
                    "temperature": 0.1,
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
            print(f"    [attempt {attempt+1}] Error: {err[:80]}")
            time.sleep(2)

    return {"conflicting": None, "conflict_type": None, "reason": "API 오류"}


def run_conflict_detection(sample_size: int = None):
    """
    FlowConflict-ONOS 74쌍으로 충돌 탐지 평가

    Args:
        sample_size: None이면 전체 74쌍, 정수면 해당 개수만 테스트
    """
    print("=== Step 2: 충돌 탐지 실험 ===\n")

    df = pd.read_csv(DATASET_PATH)
    # Yes/yes 정규화
    df["Conflicting_norm"] = df["Conflicting"].apply(normalize_label)

    if sample_size:
        df = df.sample(n=min(sample_size, len(df)), random_state=42).reset_index(drop=True)
        print(f"샘플 {len(df)}개만 실행 (전체: 74개, random_state=42)\n")
    else:
        print(f"전체 {len(df)}개 실행\n")

    y_true = []  # 정답 레이블
    y_pred = []  # 예측 레이블
    details = []
    api_errors = 0  # API 실패로 평가에서 제외된 샘플 수

    for idx, row in df.iterrows():
        rule1 = parse_flowrule(row["ONOS Flow Rule 1"])
        rule2 = parse_flowrule(row["ONOS Flow Rule 2"])
        true_label = row["Conflicting_norm"]  # "yes" or "no"
        true_type = row.get("Type of Conflict", None)

        if rule1 is None or rule2 is None:
            print(f"  [SKIP] Row {idx}: FlowRule 파싱 실패")
            continue

        print(f"  [{idx+1}/{len(df)}] 분석 중...", end=" ")
        result = detect_conflict(rule1, rule2)

        pred_conflicting = result.get("conflicting")
        pred_type = result.get("conflict_type")
        reason = result.get("reason", "")

        if pred_conflicting is None:
            # API 실패: 정확도 분모에서 제외하되 따로 카운트
            api_errors += 1
            print(f"API 오류 — 평가 제외 (누적 {api_errors}건)")
            continue

        pred_label = "yes" if pred_conflicting else "no"
        correct = pred_label == true_label

        print(f"{'OK' if correct else 'FAIL'} | 정답:{true_label} 예측:{pred_label} | {pred_type}")

        y_true.append(true_label)
        y_pred.append(pred_label)
        details.append({
            "row": int(idx),
            "true_conflicting": true_label,
            "true_type": str(true_type),
            "pred_conflicting": pred_label,
            "pred_type": pred_type,
            "reason": reason,
            "correct": correct,
        })

    # 평가 지표 계산
    evaluated = len(y_true)
    total_attempted = evaluated + api_errors

    print("\n" + "="*50)
    print("평가 결과")
    print("="*50)
    if api_errors:
        print(f"⚠  API 오류로 제외된 샘플: {api_errors}/{total_attempted}건 "
              f"(정확도는 {evaluated}건 기준)")
    print(classification_report(y_true, y_pred, target_names=["no", "yes"]))

    accuracy = sum(1 for a, b in zip(y_true, y_pred) if a == b) / evaluated * 100
    print(f"Accuracy: {accuracy:.1f}%  (평가 샘플 {evaluated}/{total_attempted})")

    return {
        "accuracy": round(accuracy, 1),
        "evaluated": evaluated,
        "api_errors": api_errors,
        "y_true": y_true,
        "y_pred": y_pred,
        "details": details,
        "report": classification_report(y_true, y_pred, target_names=["no", "yes"], output_dict=True)
    }


if __name__ == "__main__":
    # 빠른 테스트: 10개만
    result = run_conflict_detection(sample_size=10)
