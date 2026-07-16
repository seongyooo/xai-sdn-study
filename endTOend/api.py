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


# ── SSE helper ────────────────────────────────────────────────────────────────

def _sse(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


# ── Pipeline runner (synchronous, called in thread) ───────────────────────────

def _run_pipeline(req: RunRequest, q: std_queue.Queue) -> None:
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

        client = LLMClient(model=req.model)
        rag_index = rag_texts = rag_outputs = None
        if not req.no_rag and config.DATASET_PATH.exists() and req.rag_k > 0:
            try:
                rag_index, rag_texts, rag_outputs = build_index(
                    config.DATASET_PATH, client
                )
            except Exception:
                pass

        ir = IntentParser(
            client=client,
            rag_index=rag_index,
            rag_texts=rag_texts,
            rag_outputs=rag_outputs,
            k=req.rag_k,
        ).parse(req.intent)
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

        flowrule = compile_flowrule(ir)
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

        existing = None
        try:
            from stage4_twin.onos_client import OnosClient
            existing = OnosClient().flows()
        except Exception:
            pass

        static_result = static_validate(flowrule, existing_flows=existing)
        r3 = {
            "passed": static_result.passed,
            "schema_errors": static_result.schema_errors,
            "conflicts": static_result.conflicts,
            "warnings": static_result.warnings,
            "summary": static_result.summary(),
        }
        result["stage3"] = r3
        done(3, r3, t)
    except Exception as exc:
        error(3, str(exc))
        finish("REJECT")
        return

    # ── Stage 4: Digital Twin ─────────────────────────────────────────────────
    t = start(4, "Digital Twin")
    if req.skip_twin:
        from stage4_twin.twin_verifier import TwinResult
        twin_result = TwinResult(status="skipped", reason="skip_twin option")
    else:
        try:
            from stage4_twin.twin_verifier import TwinVerifier
            twin_result = TwinVerifier().verify(flowrule)
        except Exception as exc:
            from stage4_twin.twin_verifier import TwinResult
            twin_result = TwinResult(status="error", reason=str(exc))

    r4 = {
        "status": twin_result.status,
        "reason": twin_result.reason,
        "checks": twin_result.checks,
        "evidence": twin_result.evidence,
        "summary": twin_result.summary(),
    }
    result["stage4"] = r4
    s4_status = "skipped" if req.skip_twin else "done"
    emit({"type": "stage", "stage": 4, "status": s4_status,
          "result": r4, "elapsed": round(time.time() - t, 2)})

    # ── Stage 5: XAI Explanation ──────────────────────────────────────────────
    t = start(5, "XAI Explanation")
    try:
        from stage5_xai.explainer import XAIExplainer

        xai = XAIExplainer(client=client).explain(
            intent=req.intent,
            ir=ir,
            flowrule=flowrule,
            static_result=static_result,
            twin_result=twin_result,
        )
        r5 = xai.to_dict()
        decision = xai.decision
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

            dep = Deployer().deploy(flowrule)
            r6 = {"success": dep.success, "flow_ids": dep.flow_ids, "error": dep.error}
            done(6, r6, t)
        except Exception as exc:
            r6 = {"error": str(exc)}
            error(6, str(exc))
    else:
        reason = "skip_deploy option" if req.skip_deploy else f"decision={decision}"
        r6 = {"status": "skipped", "reason": reason}
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
