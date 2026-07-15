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

# ── 토폴로지 뷰 ──────────────────────────────────────────────────
st.divider()
st.subheader("🗺️ ONOS 네트워크 토폴로지")

@st.fragment(run_every=10)
def show_topology() -> None:
    """ONOS에서 토폴로지와 포트 통계를 가져와 표시 (10초마다 자동 갱신)"""
    try:
        import networkx as nx
        import matplotlib.pyplot as plt
        import matplotlib.patches as mpatches
        import pandas as pd
    except ImportError as e:
        st.warning(f"시각화 라이브러리 필요: pip install networkx matplotlib pandas\n({e})")
        return

    from stage4_twin.onos_client import OnosClient, OnosError

    client = OnosClient()

    col_graph, col_stats = st.columns([3, 2])

    # ── 그래프 ────────────────────────────────────────────────────
    with col_graph:
        try:
            devices = client.devices()
            hosts   = client.hosts()
            links   = client.links()

            G = nx.Graph()

            # 스위치 노드 추가
            for d in devices:
                dev_id    = d.get("id", "")
                available = d.get("available", False)
                # of:0000000000000001 → s1
                dpid_suffix = dev_id.lstrip("of:").lstrip("0") or "0"
                label = f"s{int(dpid_suffix, 16)}" if dpid_suffix.isalnum() else dev_id[-4:]
                G.add_node(dev_id, kind="switch", available=available, label=label)

            # 호스트 노드 추가
            for h in hosts:
                host_id = h.get("id", "")
                ips     = h.get("ipAddresses", [])
                label   = ips[0] if ips else host_id[:8]
                G.add_node(host_id, kind="host", available=True, label=label)

            # 스위치↔스위치 링크
            seen: set = set()
            for lk in links:
                src = lk.get("src", {}).get("device")
                dst = lk.get("dst", {}).get("device")
                if src and dst:
                    key = tuple(sorted([src, dst]))
                    if key not in seen:
                        G.add_edge(src, dst, kind="sw-sw")
                        seen.add(key)

            # 호스트↔스위치 링크
            for h in hosts:
                host_id   = h.get("id", "")
                locations = h.get("locations", [])
                for loc in locations:
                    dev_id = loc.get("elementId")
                    if dev_id and dev_id in G.nodes:
                        G.add_edge(host_id, dev_id, kind="host-sw")

            if G.number_of_nodes() == 0:
                st.info("ONOS에 연결된 디바이스 없음 — Docker/ONOS 실행 중인지 확인하세요.")
                return

            # 레이아웃 (스위치를 중앙에, 호스트를 외곽에)
            switch_nodes  = [n for n, d in G.nodes(data=True) if d["kind"] == "switch"]
            host_nodes    = [n for n, d in G.nodes(data=True) if d["kind"] == "host"]
            avail_sw      = [n for n in switch_nodes if G.nodes[n]["available"]]
            unavail_sw    = [n for n in switch_nodes if not G.nodes[n]["available"]]

            pos = nx.spring_layout(G, seed=42, k=2.0)

            fig, ax = plt.subplots(figsize=(7, 4))
            fig.patch.set_facecolor("#0e1117")
            ax.set_facecolor("#0e1117")

            # 엣지
            sw_sw_edges   = [(u, v) for u, v, d in G.edges(data=True) if d.get("kind") == "sw-sw"]
            host_sw_edges = [(u, v) for u, v, d in G.edges(data=True) if d.get("kind") == "host-sw"]
            nx.draw_networkx_edges(G, pos, edgelist=sw_sw_edges,
                                   edge_color="#888", width=2.0, ax=ax)
            nx.draw_networkx_edges(G, pos, edgelist=host_sw_edges,
                                   edge_color="#555", width=1.2, style="dashed", ax=ax)

            # 노드
            if avail_sw:
                nx.draw_networkx_nodes(G, pos, nodelist=avail_sw,
                                       node_color="#4CAF50", node_size=1000,
                                       node_shape="s", ax=ax)
            if unavail_sw:
                nx.draw_networkx_nodes(G, pos, nodelist=unavail_sw,
                                       node_color="#f44336", node_size=1000,
                                       node_shape="s", ax=ax)
            if host_nodes:
                nx.draw_networkx_nodes(G, pos, nodelist=host_nodes,
                                       node_color="#2196F3", node_size=600,
                                       node_shape="o", ax=ax)

            # 레이블
            labels = {n: G.nodes[n]["label"] for n in G.nodes}
            nx.draw_networkx_labels(G, pos, labels=labels, ax=ax,
                                    font_color="white", font_size=8, font_weight="bold")

            # 범례
            legend = [
                mpatches.Patch(color="#4CAF50", label="Switch (UP)"),
                mpatches.Patch(color="#f44336", label="Switch (DOWN)"),
                mpatches.Patch(color="#2196F3", label="Host"),
            ]
            ax.legend(handles=legend, loc="lower right",
                      facecolor="#1e1e1e", labelcolor="white",
                      fontsize=7, framealpha=0.8)
            ax.axis("off")
            plt.tight_layout()
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)

            # 요약 지표
            m1, m2, m3 = st.columns(3)
            m1.metric("스위치", f"{len(switch_nodes)}개 ({len(avail_sw)} UP)")
            m2.metric("호스트", f"{len(host_nodes)}개")
            m3.metric("링크", f"{len(sw_sw_edges)}개")

        except OnosError as exc:
            st.warning(f"ONOS 연결 실패 — {exc}")

    # ── 포트 통계 ─────────────────────────────────────────────────
    with col_stats:
        st.markdown("**포트 통계**")
        try:
            stats = client.port_statistics()
            rows = []
            for dev_stat in stats:
                dev_id = dev_stat.get("device", "")
                dpid   = dev_id.lstrip("of:").lstrip("0") or "0"
                sw_label = f"s{int(dpid, 16)}" if dpid.isalnum() else dev_id[-6:]
                for p in dev_stat.get("ports", []):
                    port = p.get("port", "")
                    if port == "LOCAL":
                        continue
                    rows.append({
                        "SW":      sw_label,
                        "Port":    port,
                        "Rx MB":   round(p.get("bytesReceived", 0) / 1e6, 3),
                        "Tx MB":   round(p.get("bytesSent", 0)    / 1e6, 3),
                        "Rx Pkts": p.get("packetsReceived", 0),
                        "Tx Pkts": p.get("packetsSent", 0),
                    })
            if rows:
                df = pd.DataFrame(rows)
                st.dataframe(df, use_container_width=True, hide_index=True, height=300)
            else:
                st.info("포트 통계 없음")
        except OnosError as exc:
            st.info(f"포트 통계 조회 불가: {exc}")

show_topology()

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
                from stage4_twin.twin_verifier import TwinVerifier, TwinResult
                # 플랫폼 사전 체크 — 조건 불충족 시 즉시 안내
                skip_reason = TwinVerifier._check_platform()
                if skip_reason:
                    twin_result = TwinResult(status="skipped", reason=skip_reason)
                    if "Linux" in skip_reason:
                        st.warning(
                            "⏭️ Digital Twin 스킵: Windows/macOS에서는 Mininet이 동작하지 않습니다.\n\n"
                            "WSL(Linux) 환경에서 `sudo -E streamlit run app.py` 로 실행하면 활성화됩니다."
                        )
                    elif "root" in skip_reason:
                        st.warning(
                            "⏭️ Digital Twin 스킵: root 권한이 필요합니다.\n\n"
                            "WSL 터미널에서 `sudo -E streamlit run app.py` 로 재실행하세요."
                        )
                    else:
                        st.warning(f"⏭️ Digital Twin 스킵: {skip_reason}")
                    s4.update(label="**Stage 4** — Digital Twin 검증 ⏭️", state="complete")
                else:
                    st.write("Mininet + ONOS 환경 초기화 중... (수 분 소요)")
                    buf = io.StringIO()
                    with redirect_stdout(buf):
                        verifier = TwinVerifier()
                        twin_result = verifier.verify(flowrule)

                    twin_summary = twin_result.summary()
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
