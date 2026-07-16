"""
validate_dataset.py — 데이터셋 검증 스크립트

intents_v2.jsonl 또는 임의의 JSONL 파일을 읽어
구조적 무결성, 중복 ID, 카테고리별 통계를 출력한다.

사용법:
    cd endTOend/
    python data/validate_dataset.py                         # 기본: intents_v2.jsonl
    python data/validate_dataset.py data/intents_v2.jsonl  # 경로 지정
    python data/validate_dataset.py --strict                # 오류 시 exit 1
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

_DEFAULT = Path(__file__).resolve().parent / "intents_v2.jsonl"


def _check_rule(rule: dict, rule_idx: int, case_id: str) -> list[str]:
    """단일 FlowRule dict를 검사하여 오류 메시지 목록 반환"""
    errors = []
    prefix = f"[{case_id}] rule[{rule_idx}]"

    # 필수 키
    for key in ("intent_type", "action", "selector", "enforcement"):
        if key not in rule:
            errors.append(f"{prefix} 필수 키 누락: '{key}'")

    enforcement = rule.get("enforcement")
    if enforcement is not None:
        device = enforcement.get("device", "")
        if device and not device.startswith("of:"):
            errors.append(f"{prefix} enforcement.device format error: '{device}'")

    selector = rule.get("selector") or {}
    proto = selector.get("protocol")
    if proto and proto not in ("tcp", "udp", "icmp", None):
        errors.append(f"{prefix} selector.protocol 유효하지 않음: '{proto}'")

    return errors


def validate(path: Path, strict: bool = False) -> int:
    """
    데이터셋 검증.

    Returns:
        0 — 검증 통과 (경고 있어도 OK)
        1 — 오류 발생 (strict 모드에서 exit code로 사용)
    """
    if not path.exists():
        print(f"오류: 파일이 없습니다: {path}", file=sys.stderr)
        return 1

    entries: list[dict] = []
    parse_errors = 0
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"  JSON 파싱 오류 (line {lineno}): {e}")
                parse_errors += 1

    total = len(entries)
    print(f"\n{'='*55}")
    print(f"  파일: {path}")
    print(f"  총 케이스: {total} (파싱 오류: {parse_errors})")
    print(f"{'='*55}")

    if parse_errors:
        return 1

    # ── 기본 구조 검증 ──────────────────────────────────────────
    all_errors: list[str] = []
    all_warnings: list[str] = []
    ids: list[str] = []
    category_counter: Counter = Counter()
    cohort_counter: Counter = Counter()
    status_counter: Counter = Counter()
    cat_status: dict[str, Counter] = defaultdict(Counter)

    for entry in entries:
        case_id = entry.get("id", "???")
        ids.append(case_id)

        cat = entry.get("category", "?")
        cohort = entry.get("cohort", "?")
        category_counter[cat] += 1
        cohort_counter[cohort] += 1

        # instruction 확인
        instr = entry.get("instruction", "")
        if not instr.strip():
            all_errors.append(f"[{case_id}] instruction 비어 있음")

        # expected 구조 확인
        expected = entry.get("expected")
        if not expected:
            all_errors.append(f"[{case_id}] expected 필드 누락")
            continue

        status = expected.get("status", "?")
        status_counter[status] += 1
        cat_status[cat][status] += 1

        if status == "accepted":
            program = expected.get("program") or {}
            rules = program.get("rules", [])
            if not rules:
                all_errors.append(f"[{case_id}] accepted이지만 rules가 비어 있음")
            for i, rule in enumerate(rules):
                all_errors.extend(_check_rule(rule, i, case_id))

            # SFC: sfc_chain 존재 확인
            if cat == "sfc" and "sfc_chain" not in program:
                all_warnings.append(f"[{case_id}] sfc category but no sfc_chain in program (recommended)")

        elif status == "rejected":
            rejection = expected.get("rejection")
            if not rejection:
                all_warnings.append(f"[{case_id}] rejected이지만 rejection 메시지 없음")
        else:
            all_warnings.append(f"[{case_id}] 알 수 없는 status: '{status}'")

    # ── 중복 ID ───────────────────────────────────────────────────
    id_counts = Counter(ids)
    dup_ids = [i for i, c in id_counts.items() if c > 1]
    if dup_ids:
        all_errors.append(f"중복 ID: {dup_ids}")

    # ── 통계 출력 ─────────────────────────────────────────────────
    print(f"\n카테고리별 통계:")
    for cat in sorted(category_counter):
        subtotals = " | ".join(
            f"{s}={cat_status[cat][s]}" for s in sorted(cat_status[cat])
        )
        print(f"  {cat:<12} {category_counter[cat]:>3}개   [{subtotals}]")

    print(f"\n코호트별 통계:")
    for cohort in sorted(cohort_counter):
        print(f"  {cohort:<14} {cohort_counter[cohort]:>3}개")

    print(f"\nStatus 분포: {dict(status_counter)}")

    # ── 경고 출력 ─────────────────────────────────────────────────
    if all_warnings:
        print(f"\n경고 ({len(all_warnings)}건):")
        for w in all_warnings[:20]:
            print(f"  ⚠ {w}")
        if len(all_warnings) > 20:
            print(f"  ... 외 {len(all_warnings) - 20}건")

    # ── 오류 출력 ─────────────────────────────────────────────────
    if all_errors:
        print(f"\n오류 ({len(all_errors)}건):")
        for e in all_errors[:30]:
            print(f"  [X] {e}")
        if len(all_errors) > 30:
            print(f"  ... 외 {len(all_errors) - 30}건")
        print(f"\n검증 실패: {len(all_errors)}개 오류")
        return 1
    else:
        print(f"\n[OK] 검증 통과 (총 {total}케이스, 경고 {len(all_warnings)}건)")
        return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="intents JSONL 데이터셋 검증")
    parser.add_argument(
        "path",
        nargs="?",
        default=str(_DEFAULT),
        help=f"검증할 JSONL 파일 (기본: {_DEFAULT})",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="오류 발생 시 exit code 1로 종료",
    )
    args = parser.parse_args()

    result = validate(Path(args.path), strict=args.strict)
    if args.strict:
        return result
    return 0


if __name__ == "__main__":
    sys.exit(main())
