"""
NetIntent Baseline Experiment
Intent2Flow-ONOS 데이터셋으로 3가지 방식 비교:
  Step 1: Zero-shot (베이스라인)
  Step 2: Few-shot in-context (NetIntent 방식 재현)
  Step 3: RAG (우리 방식)
"""

import os
import json
import copy
import re
import time
import pandas as pd
from sklearn.model_selection import train_test_split
from google import genai
from google.genai import types

# ── 경로 설정 ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(
    BASE_DIR,
    "NetIntent", "GitHub NetIntent", "Datasets", "Intent2Flow-ONOS.csv"
)
RESULTS_DIR = os.path.join(BASE_DIR, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)

# ── Gemini 클라이언트 ───────────────────────────────────────
client = genai.Client(api_key=os.environ.get("GOOGLE_API_KEY"))
MODEL = "gemini-3.1-flash-lite"   # 무료 티어 지원. gemini-3.1-flash-lite 사용

# ── NetIntent 프롬프트 (원문 그대로) ────────────────────────
SYSTEM_PROMPT = """Your task is to transform natural language network intents into JSON-formatted network policies compatible with the ONOS SDN controller.

You only reply in JSON, no natural language. The network intents can represent different traffic control behaviors, such as:

1. **Traffic Forwarding, Queue Assignment, and VLAN Rules:** Define rules for forwarding traffic based on IPv4/IPv6 destination, TCP/UDP ports, and optionally assign traffic to specific queues or vlans.
2. **Blocking or Dropping Rule:** Define rules to drop traffic based on specific match criteria (e.g., source IP, destination IP). In ONOS, this is done by omitting the `"treatment"` field.

### **JSON STRUCTURE FOR ONOS**

Traffic Forwarding Rule:
{
    "flows": [{
        "priority": <integer>,
        "timeout": 0,
        "isPermanent": "true",
        "deviceId": "<switch_id>",
        "treatment": {"instructions": [{"type": "OUTPUT", "port": "<integer>"}]},
        "selector": {"criteria": [
            {"type": "ETH_TYPE", "ethType": "0x800"},
            {"type": "IPV4_DST", "ip": "<ip/mask>"}
        ]}
    }]
}

Blocking Rule (no treatment field):
{
    "flows": [{
        "priority": <integer>,
        "timeout": 0,
        "isPermanent": "true",
        "deviceId": "<switch_id>",
        "selector": {"criteria": [
            {"type": "ETH_TYPE", "ethType": "0x800"},
            {"type": "IPV4_SRC", "ip": "<ip/mask>"}
        ]}
    }]
}

Field rules:
- deviceId format: "of:000000000000000X" (X = switch number as 16-digit hex)
- ethType: "0x800" for IPv4, "0x86DD" for IPv6, "0x806" for ARP
- IP_PROTO: 6=TCP, 17=UDP, 1=ICMP
- isPermanent: always "true" (string)
- Only include optional fields if explicitly mentioned
- Always respond in valid JSON only, no explanation"""


# ── 평가 함수 (NetIntent 원본) ──────────────────────────────
def normalize_value(value):
    if isinstance(value, str):
        if value.lower().startswith("0x"):
            return f"0x{int(value, 16):x}"
        elif value.isdigit():
            return int(value)
    return value


def dict_equal_ignore_order(d1, d2, ignore_fields=set()):
    if isinstance(d1, dict) and isinstance(d2, dict):
        keys1 = set(d1.keys()) - ignore_fields
        keys2 = set(d2.keys()) - ignore_fields
        if keys1 != keys2:
            return False
        for k in keys1:
            if not dict_equal_ignore_order(normalize_value(d1[k]), normalize_value(d2[k]), ignore_fields):
                return False
        return True
    elif isinstance(d1, list) and isinstance(d2, list):
        norm = lambda item: {k: normalize_value(v) for k, v in item.items()} if isinstance(item, dict) else normalize_value(item)
        n1 = sorted([norm(i) for i in d1], key=str)
        n2 = sorted([norm(i) for i in d2], key=str)
        return n1 == n2
    else:
        return normalize_value(d1) == normalize_value(d2)


def compare_onos_json(expected_json, actual_json):
    """NetIntent 원본 평가 함수: deviceId/treatment/selector 정확 비교, priority 무시"""
    exact_match_fields = ["deviceId", "isPermanent", "treatment", "selector"]
    ignore_fields = {"id", "appId", "life", "packets", "bytes", "lastSeen", "groupId", "liveType", "state"}

    expected_json = copy.deepcopy(expected_json)
    actual_json = copy.deepcopy(actual_json)

    def clean_json(j):
        for flow in j.get("flows", []):
            for f in ignore_fields:
                flow.pop(f, None)
        return j

    def normalize_json(j):
        for flow in j.get("flows", []):
            for key in ["priority", "timeout"]:
                if key in flow and isinstance(flow[key], str) and flow[key].isdigit():
                    flow[key] = int(flow[key])
            if "treatment" in flow:
                for action in flow["treatment"].get("instructions", []):
                    if "port" in action and isinstance(action["port"], str) and action["port"].isdigit():
                        action["port"] = int(action["port"])
            if "selector" in flow:
                for criterion in flow["selector"].get("criteria", []):
                    if "port" in criterion and isinstance(criterion["port"], str) and criterion["port"].isdigit():
                        criterion["port"] = int(criterion["port"])
        return j

    expected_json = normalize_json(clean_json(expected_json))
    actual_json = normalize_json(clean_json(actual_json))

    for flow in actual_json.get("flows", []):
        if "priority" not in flow or not isinstance(flow["priority"], (int, str)):
            return False

    for flow in actual_json.get("flows", []):
        if flow.get("timeout", 0) != expected_json["flows"][0].get("timeout", 0):
            return False

    for field in exact_match_fields:
        if field in expected_json["flows"][0] and field in actual_json["flows"][0]:
            if not dict_equal_ignore_order(expected_json["flows"][0][field], actual_json["flows"][0][field], ignore_fields):
                return False

    return True


def extract_switch_id(intent: str) -> str:
    ordinals = {"first":1,"second":2,"third":3,"fourth":4,"fifth":5,
                "sixth":6,"seventh":7,"eighth":8,"ninth":9,"tenth":10}
    m = re.search(r'openflow[:\s](\d+)', intent, re.IGNORECASE)
    if m:
        return f"of:{int(m.group(1)):016x}"
    m = re.search(r'\b(?:switch|router|node|openflow|device)(?:\s*number)?\s*(\d+)', intent, re.IGNORECASE)
    if m:
        return f"of:{int(m.group(1)):016x}"
    m = re.search(r'\b(?:switch|router|node|openflow|device)\s*(\w+)', intent, re.IGNORECASE)
    if m:
        word = m.group(1).lower()
        if word in ordinals:
            return f"of:{ordinals[word]:016x}"
    for word, num in ordinals.items():
        if word in intent.lower():
            return f"of:{num:016x}"
    return "of:0000000000000001"


# ── LLM 호출 ───────────────────────────────────────────────
def call_llm(system_prompt: str, user_prompt: str, max_retries: int = 5) -> dict | None:
    for attempt in range(max_retries):
        try:
            time.sleep(2)  # 무료 티어 rate limit 방지 (최대 ~30 RPM)
            resp = client.models.generate_content(
                model=MODEL,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    temperature=0.2,
                    response_mime_type="application/json",
                ),
            )
            return json.loads(resp.text)
        except Exception as e:
            err = str(e)
            print(f"  [attempt {attempt+1}] Error: {err[:80]}")
            # 429 rate limit이면 더 오래 대기
            if "429" in err:
                wait = 10 * (attempt + 1)
                print(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)
            else:
                time.sleep(2)
    return None


# ── Step 1: Zero-shot ───────────────────────────────────────
def run_zero_shot(testset: pd.DataFrame) -> dict:
    print("\n=== Step 1: Zero-shot ===")
    correct = 0
    details = []

    for _, row in testset.iterrows():
        intent = row["instruction"]
        expected = json.loads(row["output"])

        actual = call_llm(SYSTEM_PROMPT, intent)
        if actual is None:
            details.append({"intent": intent, "result": "error"})
            continue

        device_id = extract_switch_id(intent)
        for flow in actual.get("flows", []):
            flow["deviceId"] = device_id

        ok = compare_onos_json(expected, actual)
        if ok:
            correct += 1
        details.append({"intent": intent, "expected": expected, "actual": actual, "correct": ok})
        print(f"  {'OK' if ok else 'FAIL'} {intent[:60]}...")

    acc = round(correct / len(testset) * 100, 1)
    print(f"  Accuracy: {correct}/{len(testset)} = {acc}%")
    return {"step": "zero_shot", "correct": correct, "total": len(testset), "accuracy": acc, "details": details}


# ── Step 2: Few-shot (NetIntent 방식) ───────────────────────
def run_few_shot(trainset: pd.DataFrame, testset: pd.DataFrame, k: int = 3) -> dict:
    print(f"\n=== Step 2: Few-shot (k={k}) ===")
    correct = 0
    details = []

    # 간단한 고정 예시 (처음 k개, 실제 NetIntent는 MMR similarity 사용)
    examples = trainset.head(k)
    example_str = "\n\n".join(
        f"Input: {r['instruction']}\nOutput: {r['output']}"
        for _, r in examples.iterrows()
    )
    system_with_examples = SYSTEM_PROMPT + f"\n\nHere are some examples:\n\n{example_str}\n\n"

    for _, row in testset.iterrows():
        intent = row["instruction"]
        expected = json.loads(row["output"])

        actual = call_llm(system_with_examples, intent)
        if actual is None:
            details.append({"intent": intent, "result": "error"})
            continue

        device_id = extract_switch_id(intent)
        for flow in actual.get("flows", []):
            flow["deviceId"] = device_id

        ok = compare_onos_json(expected, actual)
        if ok:
            correct += 1
        details.append({"intent": intent, "expected": expected, "actual": actual, "correct": ok})
        print(f"  {'OK' if ok else 'FAIL'} {intent[:60]}...")

    acc = round(correct / len(testset) * 100, 1)
    print(f"  Accuracy: {correct}/{len(testset)} = {acc}%")
    return {"step": f"few_shot_k{k}", "correct": correct, "total": len(testset), "accuracy": acc, "details": details}


# ── Step 3: RAG ────────────────────────────────────────────
def build_rag_index(trainset: pd.DataFrame):
    """FAISS 인덱스 구축 (Gemini 임베딩)"""
    import numpy as np
    import faiss

    texts = trainset["instruction"].tolist()
    outputs = trainset["output"].tolist()

    # Gemini 임베딩
    embeddings = []
    for text in texts:
        time.sleep(0.5)
        resp = client.models.embed_content(
            model="gemini-embedding-001",
            contents=text,
        )
        embeddings.append(resp.embeddings[0].values)

    emb_matrix = np.array(embeddings, dtype="float32")
    dim = emb_matrix.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(emb_matrix)

    return index, texts, outputs, dim


def search_similar(query: str, index, texts: list, outputs: list, k: int = 3):
    """쿼리와 가장 유사한 k개 예시 검색"""
    import numpy as np

    resp = client.models.embed_content(
        model="gemini-embedding-001",
        contents=query,
    )
    q_emb = np.array([resp.embeddings[0].values], dtype="float32")
    _, indices = index.search(q_emb, k)
    return [(texts[i], outputs[i]) for i in indices[0]]


def run_rag(trainset: pd.DataFrame, testset: pd.DataFrame, k: int = 3) -> dict:
    print(f"\n=== Step 3: RAG (k={k}) ===")
    print("  Building FAISS index with Gemini embeddings...")
    index, train_texts, train_outputs, _ = build_rag_index(trainset)
    correct = 0
    details = []

    for _, row in testset.iterrows():
        intent = row["instruction"]
        expected = json.loads(row["output"])

        # 의미적으로 유사한 예시 검색
        similar = search_similar(intent, index, train_texts, train_outputs, k=k)
        example_str = "\n\n".join(
            f"Input: {txt}\nOutput: {out}" for txt, out in similar
        )
        system_with_rag = SYSTEM_PROMPT + f"\n\nRelevant examples retrieved from knowledge base:\n\n{example_str}\n\n"

        actual = call_llm(system_with_rag, intent)
        if actual is None:
            details.append({"intent": intent, "result": "error"})
            continue

        device_id = extract_switch_id(intent)
        for flow in actual.get("flows", []):
            flow["deviceId"] = device_id

        ok = compare_onos_json(expected, actual)
        if ok:
            correct += 1
        details.append({"intent": intent, "expected": expected, "actual": actual, "correct": ok})
        print(f"  {'OK' if ok else 'FAIL'} {intent[:60]}...")

    acc = round(correct / len(testset) * 100, 1)
    print(f"  Accuracy: {correct}/{len(testset)} = {acc}%")
    return {"step": f"rag_k{k}", "correct": correct, "total": len(testset), "accuracy": acc, "details": details}


# ── 메인 ────────────────────────────────────────────────────
def main():
    print("Loading Intent2Flow-ONOS dataset...")
    df = pd.read_csv(DATASET_PATH)
    print(f"Total samples: {len(df)}")

    # 50/50 split (NetIntent와 동일)
    trainset, testset = train_test_split(df, test_size=0.5, random_state=42, shuffle=True)
    print(f"Train: {len(trainset)}, Test: {len(testset)}")

    # 어떤 step만 실행할지 환경변수로 제어 (기본: 전체)
    run_steps = os.environ.get("RUN_STEPS", "1,2,3")
    steps = [s.strip() for s in run_steps.split(",")]

    results = []

    # Step 1: Zero-shot
    if "1" in steps:
        r1 = run_zero_shot(testset)
        results.append(r1)

    # Step 2: Few-shot k=3,6
    if "2" in steps:
        for k in [3, 6]:
            r2 = run_few_shot(trainset, testset, k=k)
            results.append(r2)

    # Step 3: RAG k=3,6
    if "3" in steps:
        for k in [3, 6]:
            r3 = run_rag(trainset, testset, k=k)
            results.append(r3)

    # 결과 저장
    timestamp = int(time.time())
    summary = [{"step": r["step"], "accuracy": r["accuracy"], "correct": r["correct"], "total": r["total"]} for r in results]
    summary_df = pd.DataFrame(summary)

    summary_path = os.path.join(RESULTS_DIR, f"summary_{timestamp}.csv")
    details_path = os.path.join(RESULTS_DIR, f"details_{timestamp}.json")

    summary_df.to_csv(summary_path, index=False)
    with open(details_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("\n" + "="*50)
    print("RESULTS SUMMARY")
    print("="*50)
    print(summary_df.to_string(index=False))
    print(f"\nSaved to {RESULTS_DIR}/")


if __name__ == "__main__":
    main()
