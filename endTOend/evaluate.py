"""
evaluate.py — 배치 평가 스크립트

endTOend/data/intents_v2.jsonl 을 읽어
Stage 1 (LLM 파싱) + Stage 2 (FlowRule 컴파일) 를 전수 실행하고
slot_accuracy / hallucination_rate / compile_success_rate 를 측정한다.

사용법:
    cd endTOend/
    python evaluate.py                        # 전체 케이스
    python evaluate.py --limit 10             # 첫 10케이스만 (빠른 테스트)
    python evaluate.py --skip-llm             # LLM 없이 컴파일러만 테스트
    python evaluate.py --output results.csv   # CSV 저장 경로 지정
    python evaluate.py --category sfc         # 특정 카테고리만 평가
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

# endTOend/ 를 sys.path에 추가
_BASE_DIR = Path(__file__).resolve().parent
if str(_BASE_DIR) not in sys.path:
    sys.path.insert(0, str(_BASE_DIR))

import config

# ── 데이터셋 경로 ─────────────────────────────────────────────────
_DEFAULT_DATASET = _BASE_DIR / "data" / "intents_v2.jsonl"


# ── IntentProgram → IntentIR 필드 매핑 ───────────────────────────

def _expected_ir(entry: dict) -> dict:
    """
    intents.jsonl의 expected.program.rules[0]를 IntentIR 비교용 dict로 변환.
    rejection 케이스는 None 반환.

    SFC/Reroute는 rules[0] (ingress rule)을 기준으로 평가한다.
    """
    expected = entry.get("expected", {})
    if expected.get("status") != "accepted":
        return None

    program = expected.get("program") or {}
    rules = program.get("rules", [])
    if not rules:
        return None

    rule = rules[0]
    selector = rule.get("selector") or {}
    enforcement = rule.get("enforcement") or {}
    qos = rule.get("qos") or {}

    # action 매핑 — intent_type과 action 필드를 함께 고려
    intent_type = rule.get("intent_type", "")
    action_raw = rule.get("action", "")

    if intent_type == "sfc":
        action = "sfc"
    elif intent_type == "reroute":
        action = "reroute"
    elif intent_type == "security" or action_raw == "deny":
        action = "block"
    elif intent_type == "qos" or action_raw == "prioritize":
        action = "qos"
    else:
        action = "forward"

    # device: "of:000...N" → 정수 N
    device_raw = enforcement.get("device") or ""
    device_num = None
    if device_raw.startswith("of:"):
        try:
            device_num = int(device_raw[3:], 16)
        except ValueError:
            pass

    # IP 주소 (CIDR 없이 비교)
    src = selector.get("source") or {}
    dst = selector.get("destination") or {}
    src_ip = (src.get("ip") or "").split("/")[0] or None
    dst_ip = (dst.get("ip") or "").split("/")[0] or None

    return {
        "action": action,
        "device_num": device_num,                          # int (1~4) or None
        "src_ip": src_ip,
        "dst_ip": dst_ip,
        "ip_proto": selector.get("protocol"),              # "tcp"/"udp"/"icmp"/None
        "dst_port": selector.get("destination_port"),      # int/None
        "out_port": enforcement.get("egress_port"),        # str/None
        "queue_id": qos.get("queue"),                      # int/None
    }


def _ir_to_comparable(ir) -> dict:
    """
    IntentIR 객체를 _expected_ir 와 같은 구조의 dict로 변환.
    """
    # device_hint에서 숫자 추출
    device_num = None
    hint = (ir.device_hint or "").strip()
    if hint.startswith("of:"):
        try:
            device_num = int(hint[3:], 16)
        except ValueError:
            pass
    else:
        import re
        m = re.search(r"(\d+)", hint)
        if m:
            device_num = int(m.group(1))

    return {
        "action": ir.action,
        "device_num": device_num,
        "src_ip": (ir.src_ip or "").split("/")[0] or None,
        "dst_ip": (ir.dst_ip or "").split("/")[0] or None,
        "ip_proto": ir.ip_proto,
        "dst_port": ir.dst_port,
        "out_port": str(ir.out_port) if ir.out_port is not None else None,
        "queue_id": ir.queue_id,
    }


# ── 슬롯별 정확도 계산 ────────────────────────────────────────────

SLOT_FIELDS = ["action", "device_num", "src_ip", "dst_ip", "ip_proto", "dst_port"]

def _slot_scores(pred: dict, gold: dict) -> dict[str, bool]:
    """각 슬롯의 정답 여부를 반환"""
    scores = {}
    for field in SLOT_FIELDS:
        p = pred.get(field)
        g = gold.get(field)
        # None vs None → correct
        # 문자열 비교는 소문자 정규화
        if isinstance(p, str):
            p = p.lower()
        if isinstance(g, str):
            g = g.lower()
        scores[field] = (p == g)
    return scores


def _hallucination_score(pred: dict, gold: dict) -> dict[str, bool]:
    """
    gold가 None인 필드에 pred가 값을 넣으면 hallucination.
    각 필드별 hallucination 여부 반환.
    """
    result = {}
    for field in SLOT_FIELDS:
        gold_val = gold.get(field)
        pred_val = pred.get(field)
        # gold=None인데 pred가 값을 가짐 → hallucination
        result[field] = (gold_val is None and pred_val is not None)
    return result


# ── 메인 평가 루프 ────────────────────────────────────────────────

def evaluate(
    dataset_path: Path,
    limit: Optional[int],
    skip_llm: bool,
    model: str,
    rag_k: int,
    output_path: Path,
    verbose: bool,
    category_filter: Optional[str] = None,
) -> None:

    # 데이터 로드
    entries = []
    with open(dataset_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))

    # 카테고리 필터
    if category_filter:
        entries = [e for e in entries if e.get("category") == category_filter]

    if limit:
        entries = entries[:limit]

    print(f"데이터셋: {dataset_path}")
    print(f"총 케이스: {len(entries)}개 (limit={limit}, category={category_filter or 'all'})")
    print(f"모델: {model} | RAG k={rag_k} | skip_llm={skip_llm}")
    print("=" * 60)

    # LLM/RAG 초기화
    client = parser_obj = None
    if not skip_llm:
        from stage1_intent.llm_client import LLMClient
        from stage1_intent.intent_parser import IntentParser
        from stage1_intent.rag import build_index

        client = LLMClient(model=model)
        rag_index = rag_texts = rag_outputs = None
        if rag_k > 0 and config.DATASET_PATH.exists():
            print("RAG 인덱스 구축 중...")
            try:
                rag_index, rag_texts, rag_outputs = build_index(config.DATASET_PATH, client)
            except Exception as e:
                print(f"  RAG 스킵: {e}")
        parser_obj = IntentParser(
            client=client,
            rag_index=rag_index,
            rag_texts=rag_texts,
            rag_outputs=rag_outputs,
            k=rag_k,
        )

    from stage2_flowrule.compiler import compile_flowrule, CompileError

    # 결과 수집
    rows = []
    slot_totals = {f: 0 for f in SLOT_FIELDS}
    slot_correct = {f: 0 for f in SLOT_FIELDS}
    halluc_totals = {f: 0 for f in SLOT_FIELDS}
    halluc_count = {f: 0 for f in SLOT_FIELDS}

    accepted_count = 0
    compile_ok = 0
    parse_ok = 0
    parse_fail = 0
    rejection_count = 0
    skipped_compound = 0

    for i, entry in enumerate(entries):
        eid = entry.get("id", f"#{i}")
        instruction = entry.get("instruction", "")
        category = entry.get("category", "")
        variation = entry.get("variation", "")
        expected_status = entry.get("expected", {}).get("status", "")

        row = {
            "id": eid,
            "category": category,
            "variation": variation,
            "instruction": instruction,
            "expected_status": expected_status,
            "parse_status": "",
            "compile_status": "",
        }
        for f in SLOT_FIELDS:
            row[f"pred_{f}"] = ""
            row[f"gold_{f}"] = ""
            row[f"slot_ok_{f}"] = ""
            row[f"halluc_{f}"] = ""
        row["slot_accuracy"] = ""
        row["hallucination_rate"] = ""
        row["error"] = ""

        # rejection 케이스: 별도 집계 (파이프라인 평가 대상 아님)
        if expected_status != "accepted":
            rejection_count += 1
            row["parse_status"] = "rejection_skip"
            rows.append(row)
            print(f"[{eid}] SKIP (rejection) — {instruction[:60]}")
            continue

        # compound 케이스(category="compound"): 다중 독립 인텐트 → 미지원
        # SFC/Reroute는 rules > 1이어도 단일 인텐트이므로 스킵하지 않음
        if category == "compound":
            skipped_compound += 1
            row["parse_status"] = "compound_skip"
            rows.append(row)
            print(f"[{eid}] SKIP (compound) — {instruction[:60]}")
            continue

        accepted_count += 1
        gold = _expected_ir(entry)

        # Stage 1: LLM 파싱
        ir = None
        if skip_llm:
            # LLM 없이 gold 기반 가짜 IR (컴파일러만 테스트)
            row["parse_status"] = "skipped"
        else:
            try:
                t0 = time.monotonic()
                ir = parser_obj.parse(instruction)
                elapsed = time.monotonic() - t0
                parse_ok += 1
                row["parse_status"] = f"ok ({elapsed:.1f}s)"

                pred = _ir_to_comparable(ir)

                # 슬롯 비교
                slot_scores = _slot_scores(pred, gold)
                halluc_scores = _hallucination_score(pred, gold)
                n_correct = sum(slot_scores.values())
                n_halluc = sum(halluc_scores.values())
                n_fields = len(SLOT_FIELDS)

                row["slot_accuracy"] = f"{n_correct}/{n_fields}"
                row["hallucination_rate"] = f"{n_halluc}/{n_fields}"

                for f in SLOT_FIELDS:
                    row[f"pred_{f}"] = str(pred.get(f) or "")
                    row[f"gold_{f}"] = str(gold.get(f) or "")
                    row[f"slot_ok_{f}"] = "1" if slot_scores[f] else "0"
                    row[f"halluc_{f}"] = "1" if halluc_scores[f] else "0"

                    slot_totals[f] += 1
                    if slot_scores[f]:
                        slot_correct[f] += 1
                    # hallucination은 gold=None인 필드에서만 집계
                    if gold.get(f) is None:
                        halluc_totals[f] += 1
                        if halluc_scores[f]:
                            halluc_count[f] += 1

                status_str = "✅" if n_correct == n_fields else f"⚠️ {n_correct}/{n_fields}"
                if verbose:
                    print(f"[{eid}] {status_str} | {instruction[:50]}")

            except Exception as exc:
                parse_fail += 1
                row["parse_status"] = f"error: {exc}"
                row["error"] = str(exc)
                print(f"[{eid}] PARSE ERROR — {exc}")

        # Stage 2: 컴파일러
        if ir is not None:
            try:
                flowrule = compile_flowrule(ir)
                compile_ok += 1
                row["compile_status"] = "ok"
            except CompileError as exc:
                row["compile_status"] = f"error: {exc}"
                row["error"] = str(exc)

        rows.append(row)

    # ── 집계 결과 출력 ─────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  평가 결과 요약")
    print("=" * 60)

    total_eval = accepted_count - skipped_compound
    print(f"전체: {len(entries)}개 | 평가 대상(accepted): {total_eval}개")
    print(f"  rejection 스킵: {rejection_count}개")
    print(f"  compound 스킵:  {skipped_compound}개")

    if not skip_llm and total_eval > 0:
        print(f"\n[Stage 1 LLM 파싱]")
        print(f"  성공: {parse_ok}/{total_eval}  ({100*parse_ok/total_eval:.1f}%)")
        print(f"  실패: {parse_fail}/{total_eval}")

        print(f"\n[Stage 1 슬롯 정확도]")
        all_correct = all_total = 0
        for f in SLOT_FIELDS:
            t = slot_totals[f]
            c = slot_correct[f]
            pct = 100 * c / t if t > 0 else 0
            print(f"  {f:<12}: {c}/{t}  ({pct:.1f}%)")
            all_correct += c
            all_total += t
        overall = 100 * all_correct / all_total if all_total > 0 else 0
        print(f"  {'overall':<12}: {all_correct}/{all_total}  ({overall:.1f}%)")

        print(f"\n[Stage 1 환각률 (gold=None 필드에서 값 생성)]")
        all_halluc = all_halluc_total = 0
        for f in SLOT_FIELDS:
            t = halluc_totals[f]
            h = halluc_count[f]
            pct = 100 * h / t if t > 0 else 0
            print(f"  {f:<12}: {h}/{t}  ({pct:.1f}%)")
            all_halluc += h
            all_halluc_total += t
        overall_halluc = 100 * all_halluc / all_halluc_total if all_halluc_total > 0 else 0
        print(f"  {'overall':<12}: {all_halluc}/{all_halluc_total}  ({overall_halluc:.1f}%)")

    if parse_ok > 0:
        print(f"\n[Stage 2 컴파일러]")
        print(f"  성공: {compile_ok}/{parse_ok}  ({100*compile_ok/parse_ok:.1f}%)")

    # ── CSV 저장 ──────────────────────────────────────────────────
    fieldnames = list(rows[0].keys()) if rows else []
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\n결과 저장: {output_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description="100-case 배치 평가")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=_DEFAULT_DATASET,
        help="intents.jsonl 경로",
    )
    parser.add_argument("--limit", type=int, default=None, help="평가할 최대 케이스 수")
    parser.add_argument("--skip-llm", action="store_true", help="LLM 없이 컴파일러만 테스트")
    parser.add_argument("--model", default=None, help=f"LLM 모델 (기본: {config.LLM_MODEL})")
    parser.add_argument("--rag-k", type=int, default=3, help="RAG 유사 예시 수")
    parser.add_argument(
        "--output",
        type=Path,
        default=_BASE_DIR / "logs" / "eval_results.csv",
        help="결과 CSV 저장 경로",
    )
    parser.add_argument("--verbose", action="store_true", help="케이스별 상세 출력")
    parser.add_argument(
        "--category",
        default=None,
        help="평가할 카테고리 (forwarding/security/qos/sfc/reroute/all)",
    )
    args = parser.parse_args()

    if not args.dataset.exists():
        print(f"데이터셋 없음: {args.dataset}")
        return 1

    args.output.parent.mkdir(parents=True, exist_ok=True)

    evaluate(
        dataset_path=args.dataset,
        limit=args.limit,
        skip_llm=args.skip_llm,
        model=args.model or config.LLM_MODEL,
        rag_k=args.rag_k,
        output_path=args.output,
        verbose=args.verbose,
        category_filter=args.category if args.category != "all" else None,
    )
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
