"""
app.py — XAI SDN Pipeline Streamlit UI

실행:
    cd endTOend/
    streamlit run app.py
"""
from __future__ import annotations

import json
import sys
import io
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

# ── 경로 설정 ─────────────────────────────────────────────────────
_BASE_DIR = Path(__file__).resolve().parent
if str(_BASE_DIR) not in sys.path:
    sys.path.insert(0, str(_BASE_DIR))

import config

# ── 페이지 설정 ──────────────────────────────────────────────────
st.set_page_config(
    page_title="XAI SDN Pipeline",
    page_icon="🌐",
    layout="wide",
)

st.title("🌐 XAI SDN Pipeline")
st.caption("자연어 네트워크 인텐트 → FlowRule 자동 생성 · 검증 · 배포")

# ── 사이드바: 설정 ────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ 설정")

    model = st.selectbox(
        "LLM 모델",
        ["gemini-3.1-flash-lite", "gemini-2.0-flash", "qwen3:8b", "gemma3:4b"],
        index=0,
    )

    st.divider()

    use_rag = st.toggle("RAG 사용", value=False)
    rag_k = st.slider("RAG 유사 예시 수 (k)", 1, 10, 3, disabled=not use_rag)

    st.divider()

    skip_twin = st.toggle("Digital Twin 스킵", value=True,
                          help="Linux + root + Mininet 환경에서만 실행 가능")
    skip_deploy = st.toggle("실제 ONOS 배포 스킵", value=True,
                            help="APPROVE 판정 후 실제 ONOS에 배포")

    st.divider()
    st.markdown("**ONOS 연결**")
    st.code(config.ONOS_URL, language=None)

# ── 메인: 인텐트 입력 ────────────────────────────────────────────
st.subheader("📝 네트워크 인텐트 입력")

examples = [
    "block all traffic from 10.0.0.1 to 10.0.0.4 on switch 1",
    "forward HTTP traffic from port 1 to port 2 on switch 3",
    "block TCP traffic on port 22 destined for 10.0.0.2 on switch 1",
]

col1, col2 = st.columns([3, 1])
with col1:
    intent = st.text_input(
        "인텐트",
        placeholder="block all traffic from 10.0.0.1 to 10.0.0.4 on switch 1",
        label_visibility="collapsed",
    )
with col2:
    example_pick = st.selectbox("예시", ["직접 입력"] + examples,
                                label_visibility="collapsed")

if example_pick != "직접 입력":
    intent = example_pick

run_btn = st.button("▶ 실행", type="primary", disabled=not intent.strip())

# ── 파이프라인 실행 ───────────────────────────────────────────────
if run_btn and intent.strip():
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    pipeline_result: dict = {
        "run_id": run_id,
        "intent": intent,
        "model": model,
        "rag_k": rag_k if use_rag else 0,
        "timestamp": run_id,
    }

    st.divider()
    st.subheader(f"🔄 실행 결과  `{run_id}`")

    # ── Stage 1 ───────────────────────────────────────────────────
    with st.status("**Stage 1** — 인텐트 해석 (LLM/RAG)", expanded=True) as s1:
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                from stage1_intent.llm_client import LLMClient
                from stage1_intent.intent_parser import IntentParser
                from stage1_intent.rag import build_index

                client = LLMClient(model=model)
                rag_index = rag_texts = rag_outputs = None

                if use_rag and config.DATASET_PATH.exists() and rag_k > 0:
                    st.write("RAG 인덱스 구축 중...")
                    rag_index, rag_texts, rag_outputs = build_index(
                        config.DATASET_PATH, client
                    )

                parser_obj = IntentParser(
                    client=client,
                    rag_index=rag_index,
                    rag_texts=rag_texts,
                    rag_outputs=rag_outputs,
                    k=rag_k,
                )
                ir = parser_obj.parse(intent)

            pipeline_result["stage1"] = ir.to_dict()

            st.success(
                f"action=**{ir.action}** | "
                f"src={ir.src_ip or '-'} | dst={ir.dst_ip or '-'} | "
                f"device={ir.device_hint}"
            )
            with st.expander("IntentIR 상세"):
                st.json(ir.to_dict())
            s1.update(label="**Stage 1** — 인텐트 해석 ✅", state="complete")

        except Exception as exc:
            pipeline_result["stage1"] = {"error": str(exc)}
            st.error(f"오류: {exc}")
            s1.update(label="**Stage 1** — 인텐트 해석 ❌", state="error")
            st.stop()

    # ── Stage 2 ───────────────────────────────────────────────────
    with st.status("**Stage 2** — FlowRule 컴파일", expanded=True) as s2:
        try:
            from stage2_flowrule.compiler import compile_flowrule
            flowrule = compile_flowrule(ir)
            pipeline_result["stage2"] = flowrule

            flows = flowrule.get("flows", [])
            flow = flows[0] if flows else {}
            criteria_n = len(flow.get("selector", {}).get("criteria", []))
            instructions = flow.get("treatment", {}).get("instructions", [])
            has_output = any(i.get("type") == "OUTPUT" for i in instructions)
            action_label = "FORWARD" if has_output else "DROP(차단)"

            st.success(
                f"deviceId=`{flow.get('deviceId')}` | "
                f"priority={flow.get('priority')} | "
                f"criteria={criteria_n}개 | {action_label}"
            )
            with st.expander("FlowRule JSON"):
                st.json(flowrule)
            s2.update(label="**Stage 2** — FlowRule 컴파일 ✅", state="complete")

        except Exception as exc:
            pipeline_result["stage2"] = {"error": str(exc)}
            st.error(f"오류: {exc}")
            s2.update(label="**Stage 2** — FlowRule 컴파일 ❌", state="error")
            st.stop()

    # ── Stage 3 ───────────────────────────────────────────────────
    with st.status("**Stage 3** — 정적 검증", expanded=True) as s3:
        try:
            from stage3_static.static_validator import validate as static_validate
            static_result = static_validate(flowrule, existing_flows=None)
            summary = static_result.summary()

            pipeline_result["stage3"] = {
                "passed": static_result.passed,
                "schema_errors": static_result.schema_errors,
                "conflicts": static_result.conflicts,
                "warnings": static_result.warnings,
                "summary": summary,
            }

            if static_result.passed:
                st.success(summary)
            else:
                st.warning(summary)
                if static_result.schema_errors:
                    st.error("스키마 오류: " + ", ".join(static_result.schema_errors))
                for c in static_result.conflicts:
                    st.warning(f"[{c.get('conflict_type')}] {c.get('reason', '')}")

            s3_icon = "✅" if static_result.passed else "⚠️"
            s3.update(label=f"**Stage 3** — 정적 검증 {s3_icon}", state="complete")

        except Exception as exc:
            pipeline_result["stage3"] = {"error": str(exc)}
            st.error(f"오류: {exc}")
            s3.update(label="**Stage 3** — 정적 검증 ❌", state="error")
            st.stop()

    # ── Stage 4 ───────────────────────────────────────────────────
    with st.status("**Stage 4** — Digital Twin 검증", expanded=True) as s4:
        if skip_twin:
            from stage4_twin.twin_verifier import TwinResult
            twin_result = TwinResult(status="skipped", reason="UI에서 스킵 선택")
            st.info("⏭️ Digital Twin 검증 스킵")
            s4.update(label="**Stage 4** — Digital Twin 검증 ⏭️", state="complete")
        else:
            try:
                st.write("Mininet + ONOS 환경 초기화 중... (수 분 소요)")
                buf = io.StringIO()
                with redirect_stdout(buf):
                    from stage4_twin.twin_verifier import TwinVerifier
                    verifier = TwinVerifier()
                    twin_result = verifier.verify(flowrule)

                twin_summary = twin_result.summary()
                pipeline_result["stage4"] = {
                    "status": twin_result.status,
                    "reason": twin_result.reason,
                    "checks": twin_result.checks,
                    "evidence": twin_result.evidence,
                    "summary": twin_summary,
                }

                if twin_result.status == "passed":
                    st.success(twin_summary)
                    for check, ok in twin_result.checks.items():
                        st.write(f"{'✅' if ok else '❌'} {check}")
                elif twin_result.status == "failed":
                    st.error(twin_summary)
                    for check, ok in twin_result.checks.items():
                        st.write(f"{'✅' if ok else '❌'} {check}")
                else:
                    st.warning(twin_summary)

                s4_icon = {"passed": "✅", "failed": "❌", "skipped": "⏭️", "error": "❌"}.get(
                    twin_result.status, "❓"
                )
                s4.update(label=f"**Stage 4** — Digital Twin {s4_icon}", state="complete")

            except Exception as exc:
                from stage4_twin.twin_verifier import TwinResult
                twin_result = TwinResult(status="error", reason=str(exc))
                st.error(f"오류: {exc}")
                s4.update(label="**Stage 4** — Digital Twin ❌", state="error")

        pipeline_result["stage4"] = {
            "status": twin_result.status,
            "reason": twin_result.reason,
            "checks": twin_result.checks,
            "evidence": twin_result.evidence,
            "summary": twin_result.summary(),
        }

    # ── Stage 5 ───────────────────────────────────────────────────
    with st.status("**Stage 5** — XAI 설명 생성", expanded=True) as s5:
        try:
            buf = io.StringIO()
            with redirect_stdout(buf):
                from stage5_xai.explainer import XAIExplainer
                explainer = XAIExplainer(client=client)
                xai_report = explainer.explain(
                    intent=intent,
                    ir=ir,
                    flowrule=flowrule,
                    static_result=static_result,
                    twin_result=twin_result,
                )

            decision = xai_report.decision
            pipeline_result["stage5"] = xai_report.to_dict()
            pipeline_result["decision"] = decision

            # 판정 배너
            if decision == "APPROVE":
                st.success(f"### ✅ {decision}")
            else:
                st.error(f"### ❌ {decision}")

            st.markdown(f"**판정 근거:** {xai_report.decision_reason}")

            with st.expander("단계별 요약"):
                st.markdown(f"- **인텐트 해석:** {xai_report.ir_summary}")
                st.markdown(f"- **FlowRule:** {xai_report.flowrule_summary}")
                st.markdown(f"- **정적 검증:** {xai_report.static_summary}")
                st.markdown(f"- **Digital Twin:** {xai_report.twin_summary}")

            s5.update(label="**Stage 5** — XAI 설명 ✅", state="complete")

        except Exception as exc:
            pipeline_result["stage5"] = {"error": str(exc)}
            st.error(f"오류: {exc}")
            s5.update(label="**Stage 5** — XAI 설명 ❌", state="error")
            st.stop()

    # ── Stage 6 ───────────────────────────────────────────────────
    if decision == "APPROVE" and not skip_deploy:
        with st.status("**Stage 6** — ONOS 배포", expanded=True) as s6:
            try:
                from stage6_deploy.deployer import Deployer
                deployer = Deployer()
                deploy_result = deployer.deploy(flowrule)

                if deploy_result.success:
                    st.success(deploy_result.summary())
                    pipeline_result["stage6"] = {
                        "success": True,
                        "flow_ids": deploy_result.flow_ids,
                    }
                else:
                    st.error(deploy_result.summary())
                    pipeline_result["stage6"] = {
                        "success": False,
                        "error": deploy_result.error,
                    }
                s6.update(label="**Stage 6** — ONOS 배포 ✅", state="complete")

            except Exception as exc:
                st.error(f"배포 오류: {exc}")
                pipeline_result["stage6"] = {"error": str(exc)}
                s6.update(label="**Stage 6** — ONOS 배포 ❌", state="error")

    elif decision == "APPROVE" and skip_deploy:
        pipeline_result["stage6"] = {"status": "skipped", "reason": "UI에서 스킵 선택"}
        st.info("⏭️ ONOS 배포 스킵 (설정에서 활성화 가능)")
    else:
        pipeline_result["stage6"] = {"status": "skipped", "reason": "REJECT 판정"}

    # ── 로그 저장 + 다운로드 ─────────────────────────────────────
    st.divider()
    log_path = config.LOGS_DIR / f"{run_id}.json"
    log_json = json.dumps(pipeline_result, ensure_ascii=False, indent=2, default=str)
    log_path.write_text(log_json, encoding="utf-8")

    col_a, col_b = st.columns(2)
    with col_a:
        st.download_button(
            "📥 결과 JSON 다운로드",
            data=log_json,
            file_name=f"{run_id}.json",
            mime="application/json",
        )
    with col_b:
        st.caption(f"로그 저장: `logs/{run_id}.json`")

# ── 최근 실행 기록 ────────────────────────────────────────────────
st.divider()
with st.expander("📋 최근 실행 기록"):
    log_files = sorted(config.LOGS_DIR.glob("*.json"), reverse=True)[:10]
    if not log_files:
        st.write("실행 기록 없음")
    else:
        for lf in log_files:
            try:
                data = json.loads(lf.read_text(encoding="utf-8"))
                decision_icon = "✅" if data.get("decision") == "APPROVE" else "❌"
                st.markdown(
                    f"{decision_icon} `{data.get('run_id', lf.stem)}` — "
                    f"{data.get('intent', '')[:60]}"
                )
            except Exception:
                st.markdown(f"📄 `{lf.stem}`")
