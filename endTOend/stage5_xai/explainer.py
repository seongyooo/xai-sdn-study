"""
stage5_xai/explainer.py — XAI 설명 생성 모듈

각 스테이지의 결과를 종합하여 운영자가 이해할 수 있는 자연어 설명과
결정(APPROVE/REJECT)을 생성한다.

설명 생성 전략:
  - 각 스테이지 요약: 템플릿 기반 (결정론적, 빠름)
  - decision_reason: LLM 선택적 사용 (없으면 템플릿 기반)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING

from models.intent_ir import IntentIR
from stage3_static.static_validator import StaticResult
from stage4_twin.twin_verifier import TwinResult

if TYPE_CHECKING:
    from stage1_intent.llm_client import LLMClient


@dataclass
class XAIReport:
    """XAI 파이프라인 최종 보고서"""

    intent: str                   # 원본 자연어 인텐트
    ir_summary: str               # IntentIR 해석 요약
    flowrule_summary: str         # 생성된 FlowRule 요약
    static_summary: str           # 정적 검증 결과 요약
    twin_summary: str             # Digital Twin 결과 요약
    decision: str                 # "APPROVE" | "REJECT"
    decision_reason: str          # 판정 근거
    evidence: list[dict] = field(default_factory=list)  # [{stage, finding, data}, ...]

    def to_text(self) -> str:
        """운영자용 자연어 요약 텍스트 생성"""
        lines = [
            f"인텐트: {self.intent}",
            "",
            f"[인텐트 해석] {self.ir_summary}",
            f"[FlowRule]    {self.flowrule_summary}",
            f"[정적 검증]   {self.static_summary}",
            f"[Digital Twin] {self.twin_summary}",
            "",
            f"최종 결정: {self.decision}",
            f"판정 근거: {self.decision_reason}",
        ]
        return "\n".join(lines)

    def to_dict(self) -> dict:
        """JSON 직렬화용 dict 반환"""
        return {
            "intent": self.intent,
            "ir_summary": self.ir_summary,
            "flowrule_summary": self.flowrule_summary,
            "static_summary": self.static_summary,
            "twin_summary": self.twin_summary,
            "decision": self.decision,
            "decision_reason": self.decision_reason,
            "evidence": self.evidence,
        }


class XAIExplainer:
    """XAI 설명 생성기"""

    def __init__(self, client: Optional["LLMClient"] = None) -> None:
        # LLM은 decision_reason 생성에만 선택적으로 사용
        self.client = client

    def explain(
        self,
        intent: str,
        ir: IntentIR,
        flowrule: dict,
        static_result: StaticResult,
        twin_result: TwinResult,
    ) -> XAIReport:
        """
        각 스테이지 결과를 종합하여 XAIReport를 생성한다.

        Args:
            intent: 원본 자연어 인텐트
            ir: Stage1에서 파싱된 IntentIR
            flowrule: Stage2에서 컴파일된 FlowRule dict
            static_result: Stage3 정적 검증 결과
            twin_result: Stage4 Digital Twin 결과

        Returns:
            XAIReport
        """
        # ── 1. 각 스테이지 요약 생성 (템플릿 기반) ────────────
        ir_summary = self._summarize_ir(ir)
        flowrule_summary = self._summarize_flowrule(flowrule)
        static_summary = static_result.summary()
        twin_summary = self._summarize_twin(twin_result)

        # ── 2. 결정 ───────────────────────────────────────────
        # APPROVE: 정적 검증 통과 + Digital Twin 실제 검증 통과
        # APPROVE_WITHOUT_TWIN: 정적 검증 통과 + Twin 스킵 (미검증)
        # REJECT: 정적 검증 실패 또는 Twin 실패
        if not static_result.passed or twin_result.status in ("failed", "error"):
            decision = "REJECT"
        elif twin_result.status == "skipped":
            decision = "APPROVE_WITHOUT_TWIN"
        else:
            decision = "APPROVE"

        # ── 3. 판정 근거 ──────────────────────────────────────
        decision_reason = self._build_decision_reason(
            decision, static_result, twin_result, ir
        )

        # ── 4. evidence 목록 구성 ─────────────────────────────
        evidence = self._build_evidence(ir, flowrule, static_result, twin_result)

        return XAIReport(
            intent=intent,
            ir_summary=ir_summary,
            flowrule_summary=flowrule_summary,
            static_summary=static_summary,
            twin_summary=twin_summary,
            decision=decision,
            decision_reason=decision_reason,
            evidence=evidence,
        )

    # ── 내부 요약 메서드 ──────────────────────────────────────

    def _summarize_ir(self, ir: IntentIR) -> str:
        """IntentIR을 자연어로 요약"""
        action_map = {
            "block": "차단",
            "forward": "전달",
            "qos": "QoS 처리",
            "sfc": "서비스 체인",
            "reroute": "경로 변경",
        }
        action_str = action_map.get(ir.action, ir.action)
        device_str = ir.device_hint

        parts = []
        if ir.src_ip:
            parts.append(f"src={ir.src_ip}")
        if ir.dst_ip:
            parts.append(f"dst={ir.dst_ip}")
        if ir.ip_proto:
            parts.append(f"proto={ir.ip_proto}")
        if ir.dst_port:
            parts.append(f"dport={ir.dst_port}")
        if ir.out_port:
            parts.append(f"outPort={ir.out_port}")
        if ir.queue_id:
            parts.append(f"queue={ir.queue_id}")

        match_str = " | ".join(parts) if parts else "(기본 매칭)"
        return f"action={ir.action}({action_str}) | device={device_str} | {match_str}"

    def _summarize_flowrule(self, flowrule: dict) -> str:
        """FlowRule을 한 줄로 요약"""
        flows = flowrule.get("flows", [])
        if not flows:
            return "FlowRule 없음"

        flow = flows[0]
        device_id = flow.get("deviceId", "?")
        priority = flow.get("priority", "?")
        criteria = flow.get("selector", {}).get("criteria", [])
        treatment = flow.get("treatment")
        # NOACTION instruction 또는 treatment 없음 → DROP
        # treatment is not None이어도 instructions=[{type:NOACTION}]이면 DROP
        _instructions = (treatment or {}).get("instructions", [])
        _is_drop = (
            treatment is None
            or not _instructions
            or any(i.get("type") == "NOACTION" for i in _instructions)
        )
        action_str = "DROP" if _is_drop else "FORWARD/QoS"

        return (
            f"deviceId={device_id} | priority={priority} | "
            f"criteria={len(criteria)}개 | action={action_str}"
        )

    def _summarize_twin(self, twin_result: TwinResult) -> str:
        """Digital Twin 결과 요약"""
        status_map = {
            "passed": "검증 통과",
            "failed": "검증 실패",
            "skipped": "스킵됨",
            "error": "오류 발생",
        }
        label = status_map.get(twin_result.status, twin_result.status)

        if twin_result.reason:
            return f"{label} ({twin_result.reason})"
        return label

    def _build_decision_reason(
        self,
        decision: str,
        static_result: StaticResult,
        twin_result: TwinResult,
        ir: IntentIR,
    ) -> str:
        """
        판정 근거 생성.
        LLM 클라이언트가 있으면 LLM 기반, 없으면 템플릿 기반.
        """
        # 템플릿 기반 (기본)
        reasons = []

        if static_result.passed:
            reasons.append("정적 검증 통과 (스키마 OK, 충돌 없음)")
        else:
            if static_result.schema_errors:
                reasons.append(
                    f"스키마 오류 {len(static_result.schema_errors)}개: "
                    f"{static_result.schema_errors[0]}"
                )
            if static_result.conflicts:
                conflict_types = [c.get("conflict_type", "?") for c in static_result.conflicts]
                reasons.append(
                    f"충돌 탐지 {len(static_result.conflicts)}건: {', '.join(conflict_types)}"
                )

        if twin_result.status == "passed":
            checks_ok = sum(1 for v in twin_result.checks.values() if v)
            total = len(twin_result.checks)
            reasons.append(f"Digital Twin 검증 통과 ({checks_ok}/{total} 체크)")
        elif twin_result.status == "skipped":
            reasons.append(f"Digital Twin 스킵 ({twin_result.reason})")
        elif twin_result.status == "failed":
            failed = [k for k, v in twin_result.checks.items() if not v]
            reasons.append(f"Digital Twin 실패 (실패 체크: {', '.join(failed)})")
        elif twin_result.status == "error":
            reasons.append(f"Digital Twin 오류: {twin_result.reason}")

        template_reason = "; ".join(reasons)

        # LLM 기반 (선택)
        if self.client is not None:
            llm_reason = self._llm_decision_reason(
                decision, static_result, twin_result, ir, template_reason
            )
            if llm_reason:
                return llm_reason

        return template_reason

    def _llm_decision_reason(
        self,
        decision: str,
        static_result: StaticResult,
        twin_result: TwinResult,
        ir: IntentIR,
        template_reason: str,
    ) -> Optional[str]:
        """LLM으로 판정 근거 자연어 생성 (실패 시 None 반환)"""
        system = (
            "당신은 SDN 네트워크 운영자를 위한 XAI 설명 생성기입니다. "
            "주어진 정보를 바탕으로 FlowRule 배포 판정 근거를 한국어로 2-3문장으로 설명하세요. "
            "JSON 형식: {\"reason\": \"설명 텍스트\"}"
        )
        user = (
            f"인텐트 action={ir.action}, device={ir.device_hint}\n"
            f"정적 검증: {'통과' if static_result.passed else '실패'}\n"
            f"  - 스키마 오류: {static_result.schema_errors}\n"
            f"  - 충돌: {[c.get('conflict_type') for c in static_result.conflicts]}\n"
            f"Digital Twin: {twin_result.status}\n"
            f"  - 검사 결과: {twin_result.checks}\n"
            f"최종 결정: {decision}\n"
            f"템플릿 근거: {template_reason}"
        )

        try:
            result = self.client.call(system, user)
            if result and isinstance(result.get("reason"), str):
                return result["reason"]
        except Exception:
            pass
        return None

    def _build_evidence(
        self,
        ir: IntentIR,
        flowrule: dict,
        static_result: StaticResult,
        twin_result: TwinResult,
    ) -> list[dict]:
        """각 스테이지의 evidence 목록 구성"""
        evidence = []

        # Stage 1
        evidence.append({
            "stage": "Stage1_IntentParsing",
            "finding": f"action={ir.action}, device={ir.device_hint}",
            "data": ir.to_dict(),
        })

        # Stage 2
        flows = flowrule.get("flows", [])
        flow_summary = flows[0] if flows else {}
        evidence.append({
            "stage": "Stage2_FlowRuleCompile",
            "finding": (
                f"deviceId={flow_summary.get('deviceId', '?')}, "
                f"priority={flow_summary.get('priority', '?')}"
            ),
            "data": flowrule,
        })

        # Stage 3
        evidence.append({
            "stage": "Stage3_StaticValidation",
            "finding": static_result.summary(),
            "data": {
                "passed": static_result.passed,
                "schema_errors": static_result.schema_errors,
                "conflicts": static_result.conflicts,
                "warnings": static_result.warnings,
            },
        })

        # Stage 4
        evidence.append({
            "stage": "Stage4_DigitalTwin",
            "finding": twin_result.summary(),
            "data": {
                "status": twin_result.status,
                "reason": twin_result.reason,
                "checks": twin_result.checks,
                "evidence": twin_result.evidence,
            },
        })

        return evidence
