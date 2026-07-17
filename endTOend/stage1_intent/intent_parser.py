"""
stage1_intent/intent_parser.py — 자연어 인텐트 → IntentIR 변환

LLM을 사용해 자연어를 구조화된 IntentIR로 파싱한다.
RAG가 활성화된 경우 유사 예시를 system prompt에 추가한다.
topology가 제공된 경우 시스템 프롬프트에 주입하고,
파싱 후 엔티티를 토폴로지 인벤토리와 대조하여 환각을 탐지한다.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from models.intent_ir import IntentIR, IntentPrediction

if TYPE_CHECKING:
    from stage1_intent.llm_client import LLMClient
    from models.topology import NetworkTopology

SYSTEM_PROMPT = """You are an SDN network intent parser.
Extract the user's network intent into a structured JSON with these fields:
{
  "action": "forward" | "block" | "qos" | "sfc" | "reroute",
  "device_hint": "<switch name or number as mentioned>",
  "src_ip": "<x.x.x.x/mask or null>",
  "dst_ip": "<x.x.x.x/mask or null>",
  "src_port": <int or null>,
  "dst_port": <int or null>,
  "ip_proto": "tcp" | "udp" | "icmp" | null,
  "out_port": <int or null>,
  "in_port": <int or null>,
  "alt_out_port": <int or null>,
  "waypoints": ["<device:port>" ...] | null,
  "via_device": "<switch name>" | null,
  "avoid_device": "<switch name>" | null,
  "priority": <int or null>,
  "vlan_id": <int or null>,
  "queue_id": <int or null>,
  "eth_type": "ipv4" | "ipv6" | "arp" | null
}

Action rules:
- action=block   : dropping/blocking/denying traffic
- action=forward : routing/forwarding/sending to a destination
- action=qos     : quality of service, queue assignment, prioritization
- action=sfc     : service function chaining — traffic must pass through a middlebox,
                   firewall, IDS, or inspection point before reaching destination.
                   out_port = the waypoint device port number (e.g. port 9 for firewall).
                   alt_out_port = egress port after returning from the waypoint.
                   waypoints = list of "switch:port" waypoint identifiers.
- action=reroute : path redirection, failover, bypass — sending traffic via an
                   alternative switch or port. out_port or alt_out_port = the new
                   egress port. via_device = intermediate switch to route through.
                   avoid_device = switch to bypass.

Field rules:
- If IP is mentioned without mask, append /32
- src_ip/dst_ip must be numeric IPv4 (x.x.x.x), never a hostname
- For sfc: set out_port to the waypoint port number mentioned (e.g. "port 9" → 9)
- For reroute: set out_port to the new egress port mentioned
- Respond in JSON only, no explanation."""


class IntentParser:
    """자연어 인텐트를 IntentPrediction(IntentIR 래퍼)으로 변환하는 파서"""

    def __init__(
        self,
        client: "LLMClient",
        rag_index=None,
        rag_texts: Optional[list[str]] = None,
        rag_outputs: Optional[list[str]] = None,
        k: int = 3,
        topology: Optional["NetworkTopology"] = None,
    ) -> None:
        self.client = client
        self.rag_index = rag_index
        self.rag_texts = rag_texts
        self.rag_outputs = rag_outputs
        self.k = k
        self.topology = topology

    def parse(self, intent: str) -> IntentPrediction:
        """
        자연어 인텐트를 파싱하여 IntentPrediction으로 반환한다.

        Args:
            intent: 자연어 인텐트 문자열
                예: "block all traffic from 10.0.0.1 to 10.0.0.4 on switch 1"

        Returns:
            IntentPrediction
              - status="accepted" : program 필드에 IntentIR 포함
              - status="rejected" : rejection_reason + rejection_detail 포함

        Raises:
            ValueError: LLM 응답 없음 또는 JSON 파싱 실패
        """
        system = self._build_system_prompt(intent)
        raw = self.client.call(system, intent)

        if raw is None:
            raise ValueError(
                f"LLM이 응답을 반환하지 않았습니다. 인텐트: {intent[:80]}"
            )

        ir = IntentIR.from_llm_output(raw)

        # ── 토폴로지 그라운딩 검증 ────────────────────────────────
        if self.topology is not None:
            violation = self.topology.check_intent(
                src_ip=ir.src_ip,
                dst_ip=ir.dst_ip,
                device_hint=ir.device_hint,
            )
            if violation is not None:
                reason, detail = violation
                return IntentPrediction(
                    status="rejected",
                    rejection_reason=reason,
                    rejection_detail=detail,
                )

        return IntentPrediction(status="accepted", program=ir)

    def _build_system_prompt(self, intent: str) -> str:
        """토폴로지 컨텍스트 + RAG 예시를 system prompt에 추가"""
        base = SYSTEM_PROMPT

        # 토폴로지 주입 (환각 억제)
        if self.topology is not None:
            base = self.topology.to_prompt_text() + "\n\n" + base

        # RAG 예시 추가
        if self.rag_index is not None and self.rag_texts and self.rag_outputs:
            from stage1_intent.rag import search_similar

            similar = search_similar(
                query=intent,
                index=self.rag_index,
                texts=self.rag_texts,
                outputs=self.rag_outputs,
                client=self.client,
                k=self.k,
            )

            if similar:
                examples = "\n\n".join(
                    f"Input: {txt}\nOutput: {out}" for txt, out in similar
                )
                base = (
                    base
                    + f"\n\nRelevant examples retrieved from knowledge base:\n\n{examples}\n"
                )

        return base
