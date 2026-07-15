"""
stage3_static/static_validator.py — 정적 검증 통합 모듈

스키마 검증 + 충돌 탐지를 실행하고 StaticResult를 반환한다.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from stage3_static.schema_validator import validate_schema
from stage3_static.conflict_detector import detect_conflict


@dataclass
class StaticResult:
    """정적 검증 결과"""

    passed: bool
    schema_errors: list[str] = field(default_factory=list)
    conflicts: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def summary(self) -> str:
        """운영자용 한 줄 요약"""
        parts = []

        if self.schema_errors:
            parts.append(f"스키마 오류 {len(self.schema_errors)}개")
        else:
            parts.append("Schema OK")

        if self.conflicts:
            types = [c.get("conflict_type", "?") for c in self.conflicts]
            parts.append(f"충돌 {len(self.conflicts)}개 ({', '.join(types)})")
        else:
            parts.append("충돌 없음")

        if self.warnings:
            parts.append(f"경고 {len(self.warnings)}개")

        result_str = "PASS" if self.passed else "FAIL"
        return f"{' | '.join(parts)} → {result_str}"


def validate(
    flowrule: dict,
    existing_flows: Optional[list[dict]] = None,
) -> StaticResult:
    """
    FlowRule에 대해 스키마 검증과 충돌 탐지를 실행한다.

    Args:
        flowrule: {"flows": [...]} 형식의 FlowRule dict
        existing_flows: 기존 FlowRule 목록 (None이면 충돌 탐지 스킵)

    Returns:
        StaticResult 객체
    """
    schema_errors: list[str] = []
    conflicts: list[dict] = []
    warnings: list[str] = []

    # ── Step 1: 스키마 검증 ───────────────────────────────────
    schema_result = validate_schema(flowrule)
    if not schema_result["valid"]:
        schema_errors = schema_result["errors"]

    # ── Step 2: 충돌 탐지 (스키마가 유효할 때만) ──────────────
    if not schema_errors and existing_flows:
        try:
            conflicts = detect_conflict(flowrule, existing_flows)
        except Exception as exc:
            warnings.append(f"충돌 탐지 중 오류 발생: {exc}")

    # ── 최종 판정 ─────────────────────────────────────────────
    passed = (len(schema_errors) == 0) and (len(conflicts) == 0)

    return StaticResult(
        passed=passed,
        schema_errors=schema_errors,
        conflicts=conflicts,
        warnings=warnings,
    )
