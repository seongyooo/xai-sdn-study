"""
app.py — XAI SDN Pipeline Streamlit UI

실행:
    cd endTOend/
    streamlit run app.py          # 일반
    sudo -E $(which python3) -m streamlit run app.py  # Digital Twin 사용 시
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


# ── 토폴로지 헬퍼 함수 ───────────────────────────────────────────
def _dev_label(dev_id: str) -> str:
    suffix = dev_id.replace("of:", "").lstrip("0") or "0"
    try:
        return f"s{int(suffix, 16)}"
    except ValueError:
        return dev_id[-4:]


def _parse_flows(raw_flows: list[dict]) -> list[dict]:
    rows = []
    for f in raw_flows:
        dev_id       = f.get("deviceId", "")
        criteria     = f.get("selector", {}).get("criteria", [])
        instructions = f.get("treatment", {}).get("instructions", []) if f.get("treatment") else []

        has_output   = any(i.get("type") == "OUTPUT"   for i in instructions)
        has_noaction = any(i.get("type") == "NOACTION" for i in instructions)
        if has_output:        action = "FORWARD"
        elif has_noaction or not instructions: action = "DROP"
        else:                 action = instructions[0].get("type", "?")

        match_parts = []
        for c in criteria:
            t = c.get("type", "")
            if t == "ETH_TYPE":   match_parts.append(f"eth={c.get('ethType','')}")
            elif t == "IPV4_SRC": match_parts.append(f"src={c.get('ip','')}")
            elif t == "IPV4_DST": match_parts.append(f"dst={c.get('ip','')}")
            elif t == "IP_PROTO": match_parts.append(f"proto={c.get('protocol','')}")
            elif t == "TCP_DST":  match_parts.append(f"tcp_dst={c.get('tcpPort','')}")
            elif t == "IN_PORT":  match_parts.append(f"in_port={c.get('port','')}")

        src_ip = next((c.get("ip","").split("/")[0] for c in criteria if c.get("type")=="IPV4_SRC"), None)
        dst_ip = next((c.get("ip","").split("/")[0] for c in criteria if c.get("type")=="IPV4_DST"), None)

        rows.append({
            "SW":       _dev_label(dev_id),
            "dev_id":   dev_id,
            "Priority": f.get("priority", 0),
            "Match":    ", ".join(match_parts) or "*",
            "Action":   action,
            "State":    f.get("state", ""),
            "src_ip":   src_ip,
            "dst_ip":   dst_ip,
        })
    return rows


def _draw_topology(devices, hosts, links, flow_rows):
    import networkx as nx
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches

    dev_flow_count: dict[str, int] = {}
    dev_has_drop:   dict[str, bool] = {}
    for r in flow_rows:
        did = r["dev_id"]
        dev_flow_count[did] = dev_flow_count.get(did, 0) + 1
        if r["Action"] == "DROP":
            dev_has_drop[did] = True

    G = nx.Graph()

    for d in devices:
        dev_id    = d.get("id", "")
        available = d.get("available", False)
        n_flows   = dev_flow_count.get(dev_id, 0)
        label     = f"{_dev_label(dev_id)}\n({n_flows} flows)"
        G.add_node(dev_id, kind="switch", available=available,
                   label=label, has_drop=dev_has_drop.get(dev_id, False),
                   n_flows=n_flows)

    for h in hosts:
        host_id = h.get("id", "")
        ips     = h.get("ipAddresses", [])
        ip      = ips[0] if ips else ""
        G.add_node(host_id, kind="host", label=ip or host_id[:8], ip=ip)

    seen: set = set()
    for lk in links:
        src = lk.get("src", {}).get("device")
        dst = lk.get("dst", {}).get("device")
        if src and dst:
            key = tuple(sorted([src, dst]))
            if key not in seen:
                G.add_edge(src, dst, kind="sw-sw")
                seen.add(key)

    for h in hosts:
        host_id  = h.get("id", "")
        host_ip  = G.nodes[host_id].get("ip", "") if host_id in G.nodes else ""
        for loc in h.get("locations", []):
            dev_id = loc.get("elementId")
            if dev_id and dev_id in G.nodes:
                state = "normal"
                for r in flow_rows:
                    if r["Action"] == "DROP" and (r["src_ip"] == host_ip or r["dst_ip"] == host_ip):
                        state = "blocked"; break
                    if r["Action"] == "FORWARD" and (r["src_ip"] == host_ip or r["dst_ip"] == host_ip):
                        state = "forwarded"
                G.add_edge(host_id, dev_id, kind="host-sw", flow_state=state)

    if G.number_of_nodes() == 0:
        return None, G

    switch_nodes = [n for n, d in G.nodes(data=True) if d["kind"] == "switch"]
    host_nodes   = [n for n, d in G.nodes(data=True) if d["kind"] == "host"]
    sw_sw_edges  = [(u, v) for u, v, d in G.edges(data=True) if d.get("kind") == "sw-sw"]

    sw_colors = []
    for n in switch_nodes:
        if not G.nodes[n]["available"]:       sw_colors.append("#f44336")
        elif G.nodes[n].get("has_drop"):      sw_colors.append("#FF9800")
        elif G.nodes[n].get("n_flows", 0) > 0: sw_colors.append("#8BC34A")
        else:                                 sw_colors.append("#4CAF50")

    pos = nx.spring_layout(G, seed=42, k=2.5)
    fig, ax = plt.subplots(figsize=(7, 4))
    fig.patch.set_facecolor("#0e1117")
    ax.set_facecolor("#0e1117")

    nx.draw_networkx_edges(G, pos, edgelist=sw_sw_edges,
                           edge_color="#888", width=2.0, ax=ax)
    for u, v, d in G.edges(data=True):
        if d.get("kind") != "host-sw":
            continue
        state = d.get("flow_state", "normal")
        color = {"blocked": "#f44336", "forwarded": "#4CAF50"}.get(state, "#555")
        style = "solid" if state in ("blocked", "forwarded") else "dashed"
        width = 2.0 if state != "normal" else 1.0
        nx.draw_networkx_edges(G, pos, edgelist=[(u, v)],
                               edge_color=color, width=width, style=style, ax=ax)

    if switch_nodes:
        nx.draw_networkx_nodes(G, pos, nodelist=switch_nodes,
                               node_color=sw_colors, node_size=1000,
                               node_shape="s", ax=ax)
    if host_nodes:
        nx.draw_networkx_nodes(G, pos, nodelist=host_nodes,
                               node_color="#2196F3", node_size=600,
                               node_shape="o", ax=ax)

    labels = {n: G.nodes[n]["label"] for n in G.nodes}
    nx.draw_networkx_labels(G, pos, labels=labels, ax=ax,
                            font_color="white", font_size=7, font_weight="bold")

    legend = [
        mpatches.Patch(color="#4CAF50", label="Switch (no rules)"),
        mpatches.Patch(color="#8BC34A", label="Switch (FORWARD)"),
        mpatches.Patch(color="#FF9800", label="Switch (DROP)"),
        mpatches.Patch(color="#f44336", label="Switch DOWN / Blocked"),
        mpatches.Patch(color="#4CAF50", label="Forwarded path"),
        mpatches.Patch(color="#2196F3", label="Host"),
    ]
    ax.legend(handles=legend, loc="lower right",
              facecolor="#1e1e1e", labelcolor="white",
              fontsize=6, framealpha=0.8)
    ax.axis("off")
    plt.tight_layout()
    return fig, G


# ── 토폴로지 뷰 ──────────────────────────────────────────────────
st.divider()


@st.fragment(run_every=10)
def show_topology() -> None:
    """
    ONOS 토폴로지 + FlowRule 오버레이.
    run_every=10: fragment만 10초마다 독립 rerun → 메인 페이지(파이프라인 실행)는 영향 없음.
    🔄 버튼은 fragment 내부 → 클릭 시 즉시 갱신.
    """
    try:
        import networkx as nx   # noqa: F401
        import matplotlib.pyplot as plt  # noqa: F401
        import pandas as pd
    except ImportError as e:
        st.warning(f"pip install networkx matplotlib pandas  ({e})")
        return

    from stage4_twin.onos_client import OnosClient, OnosError

    h_col, btn_col, ts_col = st.columns([4, 1, 2])
    h_col.subheader("🗺️ ONOS 네트워크 토폴로지")
    btn_col.button("🔄", key="topo_btn", help="즉시 갱신")
    # 버튼 클릭 또는 autorefresh 리런 시 항상 최신 데이터 fetch

    cache_key = "_topo_cache"
    client = OnosClient()
    from_cache = False
    try:
        devices   = client.devices()
        hosts     = client.hosts()
        links     = client.links()
        all_flows = client.flows()
        flow_rows = _parse_flows(all_flows)
        st.session_state[cache_key] = {
            "devices": devices, "hosts": hosts,
            "links": links, "flow_rows": flow_rows,
            "n_flows": len(all_flows),
            "ts": datetime.now().strftime("%H:%M:%S"),
        }
    except OnosError as exc:
        cached = st.session_state.get(cache_key)
        if cached:
            devices   = cached["devices"]
            hosts     = cached["hosts"]
            links     = cached["links"]
            flow_rows = cached["flow_rows"]
            from_cache = True
        else:
            st.warning(f"ONOS 연결 실패 — {exc}")
            return

    last_ts = st.session_state.get(cache_key, {}).get("ts", "-")
    ts_col.caption(f"최근 갱신: {last_ts}" + (" 📦캐시" if from_cache else ""))

    col_graph, col_flows = st.columns([3, 2])

    with col_graph:
        fig, G = _draw_topology(devices, hosts, links, flow_rows)
        if fig is None:
            st.info("ONOS에 연결된 디바이스 없음")
        else:
            st.pyplot(fig, use_container_width=True)
            plt.close(fig)

            switch_nodes = [n for n, d in G.nodes(data=True) if d["kind"] == "switch"]
            host_nodes   = [n for n, d in G.nodes(data=True) if d["kind"] == "host"]
            avail_sw     = [n for n in switch_nodes if G.nodes[n]["available"]]
            sw_sw_edges  = [(u, v) for u, v, d in G.edges(data=True) if d.get("kind") == "sw-sw"]
            n_flows      = st.session_state.get(cache_key, {}).get("n_flows", len(flow_rows))

            m1, m2, m3, m4 = st.columns(4)
            m1.metric("스위치", f"{len(switch_nodes)} ({len(avail_sw)} UP)")
            m2.metric("호스트", len(host_nodes))
            m3.metric("링크",   len(sw_sw_edges))
            m4.metric("FlowRule", n_flows)

    with col_flows:
        st.markdown("**현재 설치된 FlowRule**")
        if not flow_rows:
            st.info("설치된 FlowRule 없음")
        else:
            display_cols = ["SW", "Priority", "Match", "Action", "State"]
            df = pd.DataFrame(flow_rows)[display_cols]
            df["Action"] = df["Action"].map(
                lambda a: f"🔴 {a}" if a == "DROP" else (f"🟢 {a}" if a == "FORWARD" else a)
            )
            st.dataframe(df, use_container_width=True, hide_index=True, height=320)


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

            # ONOS 기존 플로우 조회 (충돌 탐지용) — 연결 실패 시 None으로 스킵
            existing_flows = None
            try:
                from stage4_twin.onos_client import OnosClient
                existing_flows = OnosClient().flows()
                if existing_flows:
                    st.caption(f"ONOS 기존 FlowRule {len(existing_flows)}개 로드 → 충돌 탐지 활성화")
            except Exception:
                st.caption("ONOS 미연결 — 기존 FlowRule 없이 스키마 검증만 수행")

            static_result = static_validate(flowrule, existing_flows=existing_flows)
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
                skip_reason = TwinVerifier._check_platform()
                if skip_reason:
                    twin_result = TwinResult(status="skipped", reason=skip_reason)
                    if "Linux" in skip_reason:
                        st.warning(
                            "⏭️ Digital Twin 스킵: Windows/macOS에서는 Mininet이 동작하지 않습니다.\n\n"
                            "WSL(Linux) 환경에서 `sudo -E $(which python3) -m streamlit run app.py` 로 실행하세요."
                        )
                    elif "root" in skip_reason:
                        st.warning(
                            "⏭️ Digital Twin 스킵: root 권한이 필요합니다.\n\n"
                            "`sudo -E $(which python3) -m streamlit run app.py` 로 재실행하세요."
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

            if decision == "APPROVE":
                st.success(f"### ✅ {decision}")
            elif decision == "APPROVE_WITHOUT_TWIN":
                st.warning(f"### ⚠️ {decision}  (Digital Twin 미검증)")
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
    if decision in ("APPROVE", "APPROVE_WITHOUT_TWIN") and not skip_deploy:
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

    elif decision in ("APPROVE", "APPROVE_WITHOUT_TWIN") and skip_deploy:
        pipeline_result["stage6"] = {"status": "skipped", "reason": "UI에서 스킵 선택"}
        st.info("⏭️ ONOS 배포 스킵 (설정에서 활성화 가능)")
    else:
        pipeline_result["stage6"] = {"status": "skipped", "reason": "REJECT 판정"}

    # ── 로그 저장 + session_state 저장 (리런 후 복원용) ──────────
    st.divider()
    log_path = config.LOGS_DIR / f"{run_id}.json"
    log_json = json.dumps(pipeline_result, ensure_ascii=False, indent=2, default=str)
    log_path.write_text(log_json, encoding="utf-8")
    st.session_state["last_pipeline_result"] = pipeline_result

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

# ── 자동 갱신 후 이전 파이프라인 결과 복원 ───────────────────────
elif "last_pipeline_result" in st.session_state:
    result = st.session_state["last_pipeline_result"]
    st.divider()
    _dec = result.get("decision", "")
    decision_icon = "✅" if _dec == "APPROVE" else ("⚠️" if _dec == "APPROVE_WITHOUT_TWIN" else "❌")
    st.subheader(f"📋 최근 실행 결과  `{result.get('run_id', '')}`")
    st.caption(f"인텐트: {result.get('intent', '')}")

    col_d, col_r = st.columns([1, 3])
    col_d.metric("판정", f"{decision_icon} {result.get('decision', '-')}")

    s5_data = result.get("stage5", {})
    if s5_data and "decision_reason" in s5_data:
        col_r.info(f"**판정 근거:** {s5_data['decision_reason']}")

    with st.expander("단계별 결과 보기"):
        cols = st.columns(3)
        for i, (stage, label) in enumerate([
            ("stage1", "Stage1 IntentIR"),
            ("stage2", "Stage2 FlowRule"),
            ("stage3", "Stage3 정적검증"),
        ]):
            with cols[i]:
                st.markdown(f"**{label}**")
                st.json(result.get(stage, {}))

        cols2 = st.columns(3)
        for i, (stage, label) in enumerate([
            ("stage4", "Stage4 Digital Twin"),
            ("stage5", "Stage5 XAI"),
            ("stage6", "Stage6 배포"),
        ]):
            with cols2[i]:
                st.markdown(f"**{label}**")
                st.json(result.get(stage, {}))

    log_json = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    st.download_button(
        "📥 결과 JSON 다운로드",
        data=log_json,
        file_name=f"{result.get('run_id', 'result')}.json",
        mime="application/json",
        key="dl_saved",
    )

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
