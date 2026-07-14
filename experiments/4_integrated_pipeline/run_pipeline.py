"""
통합 파이프라인: Experiment 1 → 2 → 3
자연어 인텐트 데이터셋을 입력받아 FlowRule 생성 → 정적 검증 → 디지털 트윈 검증까지
End-to-End로 실행한다.

Usage:
    # Gemini API (권장)
    GOOGLE_API_KEY=... sudo -E python3 run_pipeline.py --model gemini-2.0-flash

    # Ollama (로컬)
    sudo -E python3 run_pipeline.py --model qwen3:8b --onos-url http://127.0.0.1:8181/onos/v1

    # Stage 3 스킵
    python3 run_pipeline.py --model gemini-2.0-flash --skip-digital-twin
"""

from __future__ import annotations

import argparse
import importlib.util
import itertools
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
EXP1_DIR = BASE_DIR.parent / "1_netintent_baseline"
EXP2_DIR = BASE_DIR.parent / "2_static_validator"
EXP3_DIR = BASE_DIR.parent / "3_digital_twin"
RESULTS_DIR = BASE_DIR / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_DATASET = (
    EXP1_DIR / "NetIntent" / "GitHub NetIntent" / "Datasets" / "Intent2Flow-ONOS.csv"
)


# ── Gemini 백엔드 ────────────────────────────────────────────
def _is_gemini(model: str) -> bool:
    return model.lower().startswith("gemini")


def _gemini_call_llm(system_prompt: str, user_prompt: str, model: str) -> dict | None:
    """Google Gemini API로 FlowRule JSON 생성"""
    from google import genai
    from google.genai import types

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY 환경변수가 설정되지 않았습니다.")

    client = genai.Client(api_key=api_key)
    for attempt in range(6):
        try:
            response = client.models.generate_content(
                model=model,
                contents=user_prompt,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    response_mime_type="application/json",
                    temperature=0.2,
                ),
            )
            return json.loads(response.text)
        except Exception as e:
            wait = 2 ** attempt
            print(f"  [attempt {attempt+1}] Gemini error: {str(e)[:80]} — {wait}s 대기")
            time.sleep(wait)
    return None


def _gemini_embed_text(text: str) -> list[float]:
    """Google Gemini 임베딩 (gemini-embedding-001) — 429 시 지수 백오프"""
    from google import genai

    api_key = os.environ.get("GOOGLE_API_KEY")
    client = genai.Client(api_key=api_key)
    for attempt in range(6):
        try:
            result = client.models.embed_content(
                model="gemini-embedding-001",
                contents=text,
            )
            return result.embeddings[0].values
        except Exception as e:
            wait = 2 ** attempt  # 1, 2, 4, 8, 16, 32초
            print(f"\n  [embed retry {attempt+1}] {str(e)[:60]} — {wait}s 대기")
            time.sleep(wait)
    raise RuntimeError("Gemini 임베딩 실패 (재시도 초과)")


def _gemini_build_rag_index(trainset):
    """Gemini 임베딩으로 FAISS 인덱스 구축"""
    import numpy as np
    import faiss

    texts = trainset["instruction"].tolist()
    outputs = trainset["output"].tolist()

    embeddings = []
    for i, text in enumerate(texts):
        print(f"  Embedding {i+1}/{len(texts)}...", end="\r")
        embeddings.append(_gemini_embed_text(text))
        time.sleep(1)  # 분당 요청 제한 회피

    emb_matrix = np.array(embeddings, dtype="float32")
    dim = emb_matrix.shape[1]
    index = faiss.IndexFlatL2(dim)
    index.add(emb_matrix)
    return index, texts, outputs


def _gemini_search_similar(query: str, index, texts: list, outputs: list, k: int = 3):
    """Gemini 임베딩으로 유사 예시 검색"""
    import numpy as np

    q_emb = np.array([_gemini_embed_text(query)], dtype="float32")
    _, indices = index.search(q_emb, k)
    return [(texts[i], outputs[i]) for i in indices[0]]


def _gemini_detect_conflict(rule1: dict, rule2: dict) -> dict:
    """Gemini로 두 FlowRule의 충돌 여부 판단"""
    # conflict_detector.py의 프롬프트 재사용
    system_prompt = """You are an expert in SDN (Software-Defined Networking) and ONOS controller flow rules.

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

    user_prompt = f"""FlowRule 1:
{json.dumps(rule1, indent=2)}

FlowRule 2:
{json.dumps(rule2, indent=2)}

Analyze if these two ONOS FlowRules conflict."""

    model = os.environ.get("LLM_MODEL", "gemini-2.0-flash")
    result = _gemini_call_llm(system_prompt, user_prompt, model)
    if result is None:
        return {"conflicting": None, "conflict_type": None, "reason": "API 오류"}
    return result


def _gemini_explain_conflict(rule1: dict, rule2: dict, conflict_type: str) -> dict:
    """Gemini로 충돌 자연어 설명 생성"""
    system_prompt = """You are an SDN network expert explaining FlowRule conflicts to network operators.

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

    user_prompt = f"""Conflict Type: {conflict_type}

FlowRule 1:
{json.dumps(rule1, indent=2)}

FlowRule 2:
{json.dumps(rule2, indent=2)}

Explain this conflict in detail."""

    model = os.environ.get("LLM_MODEL", "gemini-2.0-flash")
    result = _gemini_call_llm(system_prompt, user_prompt, model)
    if result is None:
        return {"why": "설명 생성 실패", "impact": "", "remedy": ""}
    return result


# ── 모듈 동적 로딩 (이름 충돌 방지) ─────────────────────────
def _load_module(alias: str, filepath: Path, extra_path: Path | None = None):
    """실험별 experiment.py를 별칭으로 동적 임포트한다."""
    if extra_path:
        sys.path.insert(0, str(extra_path))
    try:
        spec = importlib.util.spec_from_file_location(alias, str(filepath))
        mod = importlib.util.module_from_spec(spec)
        sys.modules[alias] = mod
        spec.loader.exec_module(mod)
        return mod
    finally:
        if extra_path and str(extra_path) in sys.path:
            sys.path.remove(str(extra_path))


# ── Stage 1: RAG 기반 FlowRule 생성 ─────────────────────────
def stage1_generate(dataset_path: Path, model: str, rag_k: int) -> dict:
    """
    Exp 1 — RAG(k=rag_k)로 test intent 25개에 대한 FlowRule을 생성한다.

    Returns:
        {
            "method": str,
            "total": int,
            "accuracy": float,
            "results": [{"intent", "expected", "generated", "correct"}, ...]
        }
    """
    print("\n" + "=" * 60)
    print(f"[Stage 1] RAG 기반 FlowRule 생성 (model={model}, k={rag_k})")
    print("=" * 60)

    import pandas as pd
    from sklearn.model_selection import train_test_split

    exp1 = _load_module("exp1_experiment", EXP1_DIR / "experiment.py", EXP1_DIR)

    # 모델 설정 (모듈 전역 변수 갱신)
    exp1.LLM_MODEL = model

    df = pd.read_csv(dataset_path)
    trainset, testset = train_test_split(df, test_size=0.5, random_state=42, shuffle=True)
    print(f"  데이터셋: {dataset_path.name} | Train={len(trainset)}, Test={len(testset)}")

    use_gemini = _is_gemini(model)
    print(f"  백엔드: {'Gemini API' if use_gemini else 'Ollama'}")
    print(f"  FAISS 인덱스 구축 중 (train {len(trainset)}개)...")

    if use_gemini:
        index, train_texts, train_outputs = _gemini_build_rag_index(trainset)
    else:
        index, train_texts, train_outputs, _ = exp1.build_rag_index(trainset)

    correct = 0
    results = []
    for _, row in testset.iterrows():
        intent = row["instruction"]
        expected = json.loads(row["output"])

        if use_gemini:
            similar = _gemini_search_similar(intent, index, train_texts, train_outputs, k=rag_k)
        else:
            similar = exp1.search_similar(intent, index, train_texts, train_outputs, k=rag_k)

        example_str = "\n\n".join(
            f"Input: {txt}\nOutput: {out}" for txt, out in similar
        )
        system_with_rag = (
            exp1.SYSTEM_PROMPT
            + f"\n\nRelevant examples retrieved from knowledge base:\n\n{example_str}\n\n"
        )

        if use_gemini:
            generated = _gemini_call_llm(system_with_rag, intent, model)
        else:
            generated = exp1.call_llm(system_with_rag, intent)

        if generated is None:
            results.append({"intent": intent, "expected": expected, "generated": None, "correct": False})
            print(f"  [ERROR] LLM 응답 없음: {intent[:60]}...")
            continue

        device_id = exp1.extract_switch_id(intent)
        for i, flow in enumerate(generated.get("flows", [])):
            if isinstance(flow, str):
                try:
                    generated["flows"][i] = flow = json.loads(flow)
                except Exception:
                    continue
            if isinstance(flow, dict):
                flow["deviceId"] = device_id

        ok = exp1.compare_onos_json(expected, generated)
        if ok:
            correct += 1
        results.append({"intent": intent, "expected": expected, "generated": generated, "correct": ok})
        print(f"  {'OK' if ok else 'FAIL'} {intent[:60]}...")

    accuracy = round(correct / len(testset) * 100, 1)
    print(f"\n  [Stage 1] 완료 — Accuracy: {correct}/{len(testset)} = {accuracy}%")
    return {
        "method": f"rag_k{rag_k}",
        "total": len(testset),
        "correct": correct,
        "accuracy": accuracy,
        "results": results,
    }


# ── Stage 2a: Pydantic 스키마 검증 ──────────────────────────
def stage2_validate(stage1_results: list[dict]) -> dict:
    """
    Exp 2 Step 1 — 생성된 FlowRule을 Pydantic 스키마로 검증한다.

    Returns:
        {"valid": [...], "invalid": [...]}
    """
    print("\n" + "=" * 60)
    print("[Stage 2a] 스키마 검증 (Pydantic)")
    print("=" * 60)

    # validator.py는 exp2 디렉토리에 있고 모듈 이름이 중립적이므로 sys.path 추가로 임포트
    sys.path.insert(0, str(EXP2_DIR))
    try:
        from validator import validate_flowrule
    finally:
        sys.path.remove(str(EXP2_DIR))

    valid_rules = []
    invalid_rules = []

    for item in stage1_results:
        generated = item.get("generated")
        if generated is None:
            invalid_rules.append({
                "intent": item["intent"],
                "errors": ["Stage 1에서 생성 실패 (LLM 응답 없음)"],
            })
            continue

        result = validate_flowrule(generated)
        if result["valid"]:
            valid_rules.append({
                "intent": item["intent"],
                "flowrule": generated,
                "correct_in_exp1": item["correct"],
            })
            print(f"  [VALID]   {item['intent'][:60]}...")
        else:
            invalid_rules.append({
                "intent": item["intent"],
                "flowrule": generated,
                "errors": result["errors"],
            })
            print(f"  [INVALID] {item['intent'][:60]}...")
            for err in result["errors"]:
                print(f"            {err}")

    print(
        f"\n  [Stage 2a] 완료 — Valid: {len(valid_rules)}, Invalid: {len(invalid_rules)}"
    )
    return {"valid": valid_rules, "invalid": invalid_rules}


# ── Stage 2b: 충돌 탐지 ────────────────────────────────────
def stage2_conflicts(valid_rules: list[dict], max_pairs: int = 50) -> dict:
    """
    Exp 2 Step 2 — 생성된 valid FlowRule 쌍 간 충돌을 탐지한다.

    Args:
        max_pairs: 최대 검사할 쌍 수 (규모 제한). 0이면 전체.

    Returns:
        {"pairs_checked": int, "conflicts_found": int, "details": [...]}
    """
    print("\n" + "=" * 60)
    print("[Stage 2b] 충돌 탐지")
    print("=" * 60)

    use_gemini = _is_gemini(os.environ.get("LLM_MODEL", ""))

    sys.path.insert(0, str(EXP2_DIR))
    try:
        from conflict_detector import detect_conflict as _detect_conflict_ollama
    finally:
        sys.path.remove(str(EXP2_DIR))

    def detect_conflict(rule1, rule2):
        if use_gemini:
            return _gemini_detect_conflict(rule1, rule2)
        return _detect_conflict_ollama(rule1, rule2)

    pairs = list(itertools.combinations(range(len(valid_rules)), 2))
    if max_pairs and len(pairs) > max_pairs:
        print(f"  쌍 수 {len(pairs)}개 → 최대 {max_pairs}개로 제한")
        pairs = pairs[:max_pairs]

    print(f"  총 {len(pairs)}쌍 검사 중...")

    details = []
    conflicts_found = 0

    for i, j in pairs:
        rule_a = valid_rules[i]["flowrule"]
        rule_b = valid_rules[j]["flowrule"]

        # flows 배열 내 첫 번째 flow dict만 비교
        # [{}] 기본값은 실제 빈 flows: []를 커버하지 못하므로 명시적으로 처리
        flows_a = rule_a.get("flows", []) if isinstance(rule_a, dict) else []
        flows_b = rule_b.get("flows", []) if isinstance(rule_b, dict) else []
        flow_a = flows_a[0] if flows_a else {}
        flow_b = flows_b[0] if flows_b else {}

        result = detect_conflict(flow_a, flow_b)
        is_conflict = result.get("conflicting", False)
        if is_conflict:
            conflicts_found += 1

        details.append({
            "pair": [i, j],
            "intent_a": valid_rules[i]["intent"],
            "intent_b": valid_rules[j]["intent"],
            "conflicting": is_conflict,
            "conflict_type": result.get("conflict_type"),
            "reason": result.get("reason"),
        })
        status = "CONFLICT" if is_conflict else "ok"
        print(
            f"  [{status}] #{i} vs #{j} | {result.get('conflict_type', '-')} | {result.get('reason', '')[:60]}"
        )

    print(
        f"\n  [Stage 2b] 완료 — Checked: {len(pairs)}, Conflicts: {conflicts_found}"
    )
    return {
        "pairs_checked": len(pairs),
        "conflicts_found": conflicts_found,
        "details": details,
    }


# ── Stage 2c: XAI 충돌 설명 생성 ─────────────────────────
def stage2_explain(
    conflict_details: list[dict], valid_rules: list[dict]
) -> list[dict]:
    """
    Exp 2 Step 3 — 충돌 탐지된 쌍에 대해 자연어 설명을 생성한다.

    Returns:
        [{"conflict_type", "intent_a", "intent_b", "explanation": {why, impact, remedy}}, ...]
    """
    print("\n" + "=" * 60)
    print("[Stage 2c] XAI 충돌 설명 생성")
    print("=" * 60)

    conflicts = [d for d in conflict_details if d.get("conflicting")]
    if not conflicts:
        print("  충돌 없음 — 설명 생성 스킵")
        return []

    use_gemini = _is_gemini(os.environ.get("LLM_MODEL", ""))

    sys.path.insert(0, str(EXP2_DIR))
    try:
        from explainer import explain_conflict as _explain_ollama
        from explainer import format_conflict_report
    finally:
        sys.path.remove(str(EXP2_DIR))

    def explain_conflict(rule1, rule2, conflict_type):
        if use_gemini:
            return _gemini_explain_conflict(rule1, rule2, conflict_type)
        return _explain_ollama(rule1, rule2, conflict_type)

    results = []
    for c in conflicts:
        i, j = c["pair"]
        flows_a = valid_rules[i]["flowrule"].get("flows", [])
        flows_b = valid_rules[j]["flowrule"].get("flows", [])
        flow_a = flows_a[0] if flows_a else {}
        flow_b = flows_b[0] if flows_b else {}
        conflict_type = c.get("conflict_type") or "Unknown"

        print(f"  [{conflict_type}] #{i} vs #{j} 설명 생성 중...")
        explanation = explain_conflict(flow_a, flow_b, conflict_type)
        report = format_conflict_report(flow_a, flow_b, conflict_type, explanation)
        print(report)

        results.append({
            "pair": [i, j],
            "intent_a": c["intent_a"],
            "intent_b": c["intent_b"],
            "conflict_type": conflict_type,
            "explanation": explanation,
        })

    print(f"\n  [Stage 2c] 완료 — {len(results)}개 설명 생성")
    return results


# ── Stage 3: Digital Twin 검증 ────────────────────────────
def stage3_digital_twin(onos_url: str, onos_user: str, onos_password: str) -> dict:
    """
    Exp 3 — Mininet Digital Twin으로 FlowRule을 배포하고 검증한다.
    Linux + root + Mininet 환경이 필요하며, 미충족 시 자동으로 스킵된다.
    """
    print("\n" + "=" * 60)
    print("[Stage 3] Digital Twin 검증")
    print("=" * 60)

    # 환경 체크
    if sys.platform != "linux":
        reason = f"플랫폼이 Linux가 아님 (현재: {sys.platform})"
        print(f"  [SKIP] {reason}")
        return {"status": "skipped", "reason": reason}

    if os.geteuid() != 0:
        reason = "root 권한 없음 (sudo -E 로 실행하세요)"
        print(f"  [SKIP] {reason}")
        return {"status": "skipped", "reason": reason}

    try:
        import subprocess
        subprocess.run(["mn", "--version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        reason = "Mininet(mn)이 설치되지 않음"
        print(f"  [SKIP] {reason}")
        return {"status": "skipped", "reason": reason}

    # Exp 3 모듈 로드 (onos_client, topology도 같은 디렉토리)
    sys.path.insert(0, str(EXP3_DIR))
    try:
        exp3 = _load_module("exp3_experiment", EXP3_DIR / "experiment.py", EXP3_DIR)
        from onos_client import OnosClient, OnosError

        controller_ip = "127.0.0.1"
        controller_port = 6653
        client = OnosClient(onos_url, onos_user, onos_password)

        try:
            result = exp3.run_experiment(client, controller_ip, controller_port)
            status = "passed" if result["passed"] else "failed"
            print(f"\n  [Stage 3] 완료 — {status.upper()}")
            return {"status": status, **result}
        except (OnosError, PermissionError, RuntimeError, ValueError) as exc:
            print(f"  [ERROR] {exc}")
            return {"status": "error", "reason": str(exc)}
    finally:
        if str(EXP3_DIR) in sys.path:
            sys.path.remove(str(EXP3_DIR))


# ── 메인 ─────────────────────────────────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(
        description="End-to-End XAI Pipeline: Exp1 → Exp2 → Exp3"
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_DATASET,
        help="인텐트 CSV 경로 (기본: Intent2Flow-ONOS.csv)",
    )
    parser.add_argument("--model", default="qwen3:8b", help="LLM 모델 이름")
    parser.add_argument("--rag-k", type=int, default=3, help="RAG k 값 (기본 3)")
    parser.add_argument(
        "--max-conflict-pairs",
        type=int,
        default=50,
        help="충돌 탐지 최대 쌍 수 (0=전체, 기본 50)",
    )
    parser.add_argument(
        "--skip-digital-twin",
        action="store_true",
        help="Exp 3 Digital Twin 강제 스킵",
    )
    parser.add_argument(
        "--onos-url",
        default="http://127.0.0.1:8181/onos/v1",
        help="ONOS REST API URL",
    )
    parser.add_argument(
        "--onos-user",
        default=os.environ.get("ONOS_USER", "onos"),
    )
    parser.add_argument(
        "--onos-password",
        default=os.environ.get("ONOS_PASSWORD", "rocks"),
    )
    args = parser.parse_args()

    # 환경 변수로 LLM 모델 전파 (exp2 모듈들이 사용)
    os.environ["LLM_MODEL"] = args.model

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    print(f"\n{'='*60}")
    print(f"  통합 파이프라인 시작  run_id={run_id}")
    print(f"  모델: {args.model} | RAG k={args.rag_k}")
    print(f"  데이터셋: {args.dataset}")
    print(f"{'='*60}")

    pipeline_result: dict = {
        "run_id": run_id,
        "model": args.model,
        "rag_k": args.rag_k,
        "dataset": str(args.dataset),
    }

    # ── Stage 1 ──────────────────────────────────────────
    s1 = stage1_generate(args.dataset, args.model, args.rag_k)
    pipeline_result["stage1_generation"] = {
        "method": s1["method"],
        "total": s1["total"],
        "correct": s1["correct"],
        "accuracy": s1["accuracy"],
        "results": s1["results"],
    }

    # ── Stage 2a ─────────────────────────────────────────
    s2a = stage2_validate(s1["results"])
    pipeline_result["stage2_validation"] = {
        "valid_count": len(s2a["valid"]),
        "invalid_count": len(s2a["invalid"]),
        "invalid_details": [
            {"intent": r["intent"], "errors": r["errors"]}
            for r in s2a["invalid"]
        ],
    }

    # ── Stage 2b ─────────────────────────────────────────
    if s2a["valid"]:
        s2b = stage2_conflicts(s2a["valid"], max_pairs=args.max_conflict_pairs)
        pipeline_result["stage2_conflicts"] = s2b

        # ── Stage 2c ─────────────────────────────────────
        s2c = stage2_explain(s2b["details"], s2a["valid"])
        pipeline_result["stage2_explanations"] = s2c
    else:
        print("\n  [Stage 2b/2c] 유효한 FlowRule 없음 — 스킵")
        pipeline_result["stage2_conflicts"] = {"pairs_checked": 0, "conflicts_found": 0, "details": []}
        pipeline_result["stage2_explanations"] = []

    # ── Stage 3 ──────────────────────────────────────────
    # TODO (논문 한계): Stage 3는 현재 experiment.py에 하드코딩된 DROP_RULE을 사용하며,
    # Stage 2에서 생성·검증된 FlowRule을 실제 Mininet에 배포하지 않는다.
    # 진정한 End-to-End 파이프라인 검증을 위해서는 stage2_validate()의 valid 결과 중
    # 대표 FlowRule을 추출하여 exp3.run_experiment()에 전달해야 한다.
    if args.skip_digital_twin:
        pipeline_result["stage3_digital_twin"] = {
            "status": "skipped",
            "reason": "--skip-digital-twin 플래그",
        }
        print("\n[Stage 3] --skip-digital-twin 플래그로 스킵")
    else:
        s3 = stage3_digital_twin(args.onos_url, args.onos_user, args.onos_password)
        pipeline_result["stage3_digital_twin"] = s3

    # ── 결과 저장 ─────────────────────────────────────────
    timestamp = int(time.time())
    output_path = RESULTS_DIR / f"pipeline_{timestamp}.json"
    output_path.write_text(
        json.dumps(pipeline_result, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # ── 최종 요약 ─────────────────────────────────────────
    print("\n" + "=" * 60)
    print("통합 파이프라인 최종 요약")
    print("=" * 60)

    s1r = pipeline_result["stage1_generation"]
    print(f"  Stage 1  FlowRule 생성  : {s1r['correct']}/{s1r['total']} = {s1r['accuracy']}% 정확도")

    s2vr = pipeline_result["stage2_validation"]
    print(f"  Stage 2a 스키마 검증    : Valid {s2vr['valid_count']} / Invalid {s2vr['invalid_count']}")

    s2cr = pipeline_result["stage2_conflicts"]
    print(f"  Stage 2b 충돌 탐지      : {s2cr['pairs_checked']}쌍 중 {s2cr['conflicts_found']}건 충돌")

    exps = pipeline_result["stage2_explanations"]
    print(f"  Stage 2c XAI 설명       : {len(exps)}건 설명 생성")

    s3r = pipeline_result["stage3_digital_twin"]
    print(f"  Stage 3  Digital Twin   : {s3r['status'].upper()}")
    if s3r.get("reason"):
        print(f"           ({s3r['reason']})")

    print(f"\n  결과 저장: {output_path}")
    print("=" * 60)

    # Stage 3가 실패한 경우만 비정상 종료
    if s3r.get("status") == "failed":
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
