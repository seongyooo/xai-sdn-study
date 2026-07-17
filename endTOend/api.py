"""
FastAPI backend for XAI-SDN Pipeline
실행: uvicorn api:app --reload --port 8000
     (endTOend/ 디렉토리에서 실행)
"""
from __future__ import annotations

import asyncio
import json
import queue as std_queue
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

_BASE_DIR = Path(__file__).resolve().parent
if str(_BASE_DIR) not in sys.path:
    sys.path.insert(0, str(_BASE_DIR))

import config

app = FastAPI(title="XAI-SDN Pipeline API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class RunRequest(BaseModel):
    intent: str
    model: str = config.LLM_MODEL
    rag_k: int = 3
    no_rag: bool = False
    skip_twin: bool = False
    skip_deploy: bool = False

    def validate_intent(self) -> str | None:
        """빈 인텐트면 오류 메시지 반환, 정상이면 None"""
        if not self.intent.strip():
            return "인텐트가 비어 있습니다."
        return None


# ── SSE helper ────────────────────────────────────────────────────────────────

def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


# ── Pipeline runner (synchronous, called in thread) ───────────────────────────

def _run_pipeline(req: RunRequest, q: std_queue.Queue) -> None:
    # 빈 인텐트 조기 거부
    if err := req.validate_intent():
        q.put(_sse({"type": "error", "stage": 0, "error": err}))
        q.put(_sse({"type": "done"}))
        return

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    result: dict = {
        "run_id": run_id,
        "intent": req.intent,
        "model": req.model,
        "rag_k": req.rag_k,
        "timestamp": run_id,
    }
    client = None

    def emit(data: dict) -> None:
        q.put(_sse(data))

    def progress(n: int, msg: str) -> None:
        emit({"type": "progress", "stage": n, "msg": msg})

    def start(n: int, name: str) -> float:
        emit({"type": "stage", "stage": n, "status": "running", "name": name})
        return time.time()

    def done(n: int, res: dict, t0: float) -> None:
        emit({"type": "stage", "stage": n, "status": "done",
              "result": res, "elapsed": round(time.time() - t0, 2)})

    def error(n: int, err: str) -> None:
        emit({"type": "stage", "stage": n, "status": "error", "error": err})

    def finish(decision: str) -> None:
        result["decision"] = decision
        (config.LOGS_DIR / f"{run_id}.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )
        emit({"type": "decision", "decision": decision,
              "report": result.get("stage5", {})})
        emit({"type": "done", "run_id": run_id})

    # ── Stage 1: Intent Parsing ───────────────────────────────────────────────
    t = start(1, "Intent Parsing")
    try:
        from stage1_intent.llm_client import LLMClient
        from stage1_intent.intent_parser import IntentParser
        from stage1_intent.rag import build_index

        progress(1, f"LLM 클라이언트 초기화 중... (모델: {req.model})")
        client = LLMClient(model=req.model)

        rag_index = rag_texts = rag_outputs = None
        if not req.no_rag and config.DATASET_PATH.exists() and req.rag_k > 0:
            try:
                progress(1, f"RAG 인덱스 구축 중... (유사 예시 k={req.rag_k})")
                rag_index, rag_texts, rag_outputs = build_index(
                    config.DATASET_PATH, client
                )
                progress(1, f"RAG 완료 — {len(rag_texts) if rag_texts else 0}개 예시 임베딩됨")
            except Exception as rag_exc:
                progress(1, f"RAG 스킵 (오류: {str(rag_exc)[:60]})")
        elif req.no_rag:
            progress(1, "RAG 비활성화 — LLM 직접 호출")
        else:
            progress(1, "데이터셋 없음 — RAG 스킵")

        from models.topology import NetworkTopology
        topology = NetworkTopology.diamond()

        progress(1, "인텐트 파싱 중... (LLM 호출)")
        prediction = IntentParser(
            client=client,
            rag_index=rag_index,
            rag_texts=rag_texts,
            rag_outputs=rag_outputs,
            k=req.rag_k,
            topology=topology,
        ).parse(req.intent)

        # 토폴로지 그라운딩 거부 처리
        if prediction.status == "rejected":
            reason = prediction.rejection_reason or "unknown"
            detail = prediction.rejection_detail or ""
            progress(1, f"인텐트 거부 [{reason}]: {detail}")
            result["stage1"] = {"status": "rejected", "rejection_reason": reason,
                                "rejection_detail": detail}
            error(1, f"[{reason}] {detail}")
            finish("REJECT")
            return

        ir = prediction.program
        progress(1, f"파싱 완료 → action={ir.action}, device={ir.device_hint}"
                    + (f", src={ir.src_ip}" if ir.src_ip else "")
                    + (f", dst={ir.dst_ip}" if ir.dst_ip else ""))
        result["stage1"] = ir.to_dict()
        done(1, ir.to_dict(), t)
    except Exception as exc:
        error(1, str(exc))
        finish("REJECT")
        return

    # ── Stage 2: FlowRule Compile ─────────────────────────────────────────────
    t = start(2, "FlowRule Compile")
    try:
        from stage2_flowrule.compiler import compile_flowrule

        progress(2, f"device_hint 변환 중... ({ir.device_hint!r} → ONOS device ID)")
        progress(2, f"OpenFlow criteria 생성 중... (action={ir.action})")
        flowrule = compile_flowrule(ir)
        flows = flowrule.get("flows", [])
        f0 = flows[0] if flows else {}
        criteria_n = len(f0.get("selector", {}).get("criteria", []))
        priority = f0.get("priority", "?")
        device_id = f0.get("deviceId", "?")
        progress(2, f"컴파일 완료 → deviceId={device_id}, priority={priority}, criteria={criteria_n}개")
        result["stage2"] = flowrule
        done(2, flowrule, t)
    except Exception as exc:
        error(2, str(exc))
        finish("REJECT")
        return

    # ── Stage 3: Static Validation ────────────────────────────────────────────
    t = start(3, "Static Validation")
    try:
        from stage3_static.static_validator import validate as static_validate

        progress(3, "ONOS 기존 플로우 조회 중...")
        existing = None
        try:
            from stage4_twin.onos_client import OnosClient
            existing = OnosClient().flows()
            progress(3, f"기존 플로우 {len(existing) if existing else 0}개 수신")
        except Exception:
            progress(3, "ONOS 연결 실패 — 충돌 탐지 없이 스키마만 검증")

        progress(3, "스키마 검증 중... (ONOS FlowRule 형식 확인)")
        progress(3, "충돌 탐지 중... (Shadowing / Correlation / Imbrication)")
        static_result = static_validate(flowrule, existing_flows=existing)
        r3 = {
            "passed": static_result.passed,
            "schema_errors": static_result.schema_errors,
            "conflicts": static_result.conflicts,
            "warnings": static_result.warnings,
            "summary": static_result.summary(),
        }
        if static_result.warnings:
            for w in static_result.warnings:
                progress(3, f"⚠ 경고: {w[:100]}")
        if static_result.conflicts:
            for c in static_result.conflicts:
                progress(3, f"✗ 충돌: [{c.get('conflict_type')}] {c.get('reason','')[:80]}")
        progress(3, f"검증 결과: {'PASS' if static_result.passed else 'FAIL'}")
        result["stage3"] = r3
        done(3, r3, t)
    except Exception as exc:
        error(3, str(exc))
        finish("REJECT")
        return

    # ── Stage 4: Digital Twin ─────────────────────────────────────────────────
    t = start(4, "Digital Twin")
    if req.skip_twin:
        progress(4, "Skip Digital Twin 옵션 활성화 — 건너뜀")
        from stage4_twin.twin_verifier import TwinResult
        twin_result = TwinResult(status="skipped", reason="skip_twin option")
    else:
        try:
            from stage4_twin.twin_verifier import TwinVerifier, TwinResult
            progress(4, "플랫폼 환경 확인 중... (Linux + root + Mininet 필요)")
            verifier = TwinVerifier()
            # 플랫폼 체크 결과 미리 확인
            skip_reason = verifier._check_platform()
            if skip_reason:
                progress(4, f"환경 조건 미충족 — {skip_reason}")
            else:
                progress(4, "Mininet 토폴로지 구성 중...")
                progress(4, "ONOS 컨트롤러 연결 중...")
                progress(4, "FlowRule 배포 및 트래픽 검증 중...")
            twin_result = verifier.verify(flowrule)
            if twin_result.checks:
                for chk, ok in twin_result.checks.items():
                    progress(4, f"{'✓' if ok else '✗'} {chk}: {'통과' if ok else '실패'}")
        except Exception as exc:
            from stage4_twin.twin_verifier import TwinResult
            twin_result = TwinResult(status="error", reason=str(exc))
            progress(4, f"오류 발생: {str(exc)[:100]}")

    r4 = {
        "status": twin_result.status,
        "reason": twin_result.reason,
        "checks": twin_result.checks,
        "evidence": twin_result.evidence,
        "summary": twin_result.summary(),
    }
    result["stage4"] = r4
    s4_status = "skipped" if twin_result.status == "skipped" else "done"
    emit({"type": "stage", "stage": 4, "status": s4_status,
          "result": r4, "elapsed": round(time.time() - t, 2)})

    # ── Stage 5: XAI Explanation ──────────────────────────────────────────────
    t = start(5, "XAI Explanation")
    try:
        from stage5_xai.explainer import XAIExplainer

        progress(5, "각 단계 결과 종합 중...")
        progress(5, f"정적 검증: {'PASS' if static_result.passed else 'FAIL'} | "
                    f"Digital Twin: {twin_result.status}")
        progress(5, "최종 판정 계산 중...")
        progress(5, f"XAI 판정 근거 생성 중... (LLM 호출: {req.model})")
        xai = XAIExplainer(client=client).explain(
            intent=req.intent,
            ir=ir,
            flowrule=flowrule,
            static_result=static_result,
            twin_result=twin_result,
        )
        r5 = xai.to_dict()
        decision = xai.decision
        progress(5, f"최종 결정: {decision}")
        result["stage5"] = r5
        done(5, r5, t)
    except Exception as exc:
        error(5, str(exc))
        finish("REJECT")
        return

    # ── Stage 6: ONOS Deploy ──────────────────────────────────────────────────
    t = start(6, "ONOS Deploy")
    if decision in ("APPROVE", "APPROVE_WITHOUT_TWIN") and not req.skip_deploy:
        try:
            from stage6_deploy.deployer import Deployer

            progress(6, "배포 전 ONOS 플로우 스냅샷 수집 중...")
            progress(6, f"FlowRule POST → {config.ONOS_URL}/flows")
            dep = Deployer().deploy(flowrule)
            r6 = {"success": dep.success, "flow_ids": dep.flow_ids, "error": dep.error}
            if dep.success:
                progress(6, f"배포 완료 — 신규 flow ID: {dep.flow_ids}")
            else:
                progress(6, f"배포 실패: {dep.error}")
            done(6, r6, t)
        except Exception as exc:
            r6 = {"error": str(exc)}
            error(6, str(exc))
    elif req.skip_deploy:
        progress(6, "Skip ONOS Deploy 옵션 활성화 — 건너뜀")
        r6 = {"status": "skipped", "reason": "skip_deploy option"}
        emit({"type": "stage", "stage": 6, "status": "skipped",
              "result": r6, "elapsed": 0})
    else:
        progress(6, f"decision={decision} — 배포 조건 미충족, 건너뜀")
        r6 = {"status": "skipped", "reason": f"decision={decision}"}
        emit({"type": "stage", "stage": 6, "status": "skipped",
              "result": r6, "elapsed": 0})
    result["stage6"] = r6

    finish(decision)


# ── API Routes ────────────────────────────────────────────────────────────────

@app.post("/api/run")
async def run_pipeline(req: RunRequest):
    q: std_queue.Queue = std_queue.Queue()

    async def stream():
        loop = asyncio.get_event_loop()
        fut = loop.run_in_executor(None, _run_pipeline, req, q)
        while True:
            try:
                msg = q.get_nowait()
                yield msg
                if '"type": "done"' in msg:
                    break
            except std_queue.Empty:
                if fut.done():
                    # Thread finished — drain any remaining events that arrived
                    # just before fut.done() was observed (no more will be added)
                    while True:
                        try:
                            msg = q.get_nowait()
                            yield msg
                            if '"type": "done"' in msg:
                                await fut
                                return
                        except std_queue.Empty:
                            break
                    break
                await asyncio.sleep(0.05)
                yield ": keepalive\n\n"
        await fut

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.get("/api/topology")
def get_topology():
    try:
        from stage4_twin.onos_client import OnosClient

        c = OnosClient()
        devices = c.devices() or []
        hosts_data = c.hosts() or []
        links_data = c.links() or []
        flows_data = c.flows() or []

        # Map device → action types from its flow rules
        dev_actions: dict[str, set] = {}
        for f in flows_data:
            did = f.get("deviceId", "")
            for inst in f.get("treatment", {}).get("instructions", []):
                dev_actions.setdefault(did, set()).add(inst.get("type", ""))

        def dev_state(did: str, avail: bool) -> str:
            if not avail:
                return "offline"
            acts = dev_actions.get(did, set())
            if "NOACTION" in acts:
                return "drop"
            if "OUTPUT" in acts:
                return "forward"
            return "idle"

        nodes = [
            {
                "id": d["id"],
                "label": f"S{i + 1}",
                "type": "switch",
                "state": dev_state(d["id"], d.get("available", False)),
            }
            for i, d in enumerate(devices)
        ]
        dev_label = {n["id"]: n["label"] for n in nodes}

        host_nodes = [
            {
                "id": h["id"],
                "label": f"H{j + 1}",
                "type": "host",
                "ip": (h.get("ipAddresses") or [""])[0],
                "switch": (h.get("locations") or [{}])[0].get("elementId", ""),
            }
            for j, h in enumerate(hosts_data)
        ]

        seen: set = set()
        links = []
        for lnk in links_data:
            src = lnk.get("src", {}).get("device", "")
            dst = lnk.get("dst", {}).get("device", "")
            k = tuple(sorted([src, dst]))
            if k not in seen:
                seen.add(k)
                links.append({"source": src, "target": dst})
        for h in host_nodes:
            if h["switch"]:
                links.append({"source": h["id"], "target": h["switch"]})

        # Flow table (first 20 rules)
        flow_table = []
        for f in flows_data[:20]:
            did = f.get("deviceId", "")
            criteria = f.get("selector", {}).get("criteria", [])
            match_parts = []
            for c in criteria[:2]:
                val = c.get("ip") or c.get("port") or c.get("mac") or c.get("ethType") or ""
                if val:
                    match_parts.append(f"{c.get('type', '?')}={val}")
            instructions = f.get("treatment", {}).get("instructions", [])
            is_drop = not instructions or all(
                i.get("type") in ("NOACTION", "DROP") for i in instructions
            )
            flow_table.append({
                "device": dev_label.get(did, did[-4:] if len(did) > 4 else did),
                "priority": f.get("priority", 0),
                "match": ", ".join(match_parts) or "—",
                "action": "DROP" if is_drop else "FORWARD",
            })

        return {
            "nodes": nodes + host_nodes,
            "links": links,
            "flow_table": flow_table,
            "rule_count": len(flows_data),
            "error": None,
        }
    except Exception as exc:
        return {"nodes": [], "links": [], "flow_table": [], "rule_count": 0, "error": str(exc)}


@app.get("/api/logs")
def get_logs():
    entries = []
    for f in sorted(config.LOGS_DIR.glob("*.json"), reverse=True)[:10]:
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
            entries.append({
                "run_id": d.get("run_id", ""),
                "intent": d.get("intent", ""),
                "decision": d.get("decision", ""),
                "timestamp": d.get("timestamp", ""),
            })
        except Exception:
            continue
    return entries


# ── Static files (must be last) ───────────────────────────────────────────────
_static = _BASE_DIR / "static"
_static.mkdir(exist_ok=True)
app.mount("/", StaticFiles(directory=str(_static), html=True), name="static")
