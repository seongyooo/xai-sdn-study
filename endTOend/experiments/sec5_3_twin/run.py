"""
sec5_3_twin/run.py — 논문 Section 5.3: Digital Twin 검증 결과

block intent 3종 + forward intent 3종 총 6개 인텐트를 파이프라인으로 실행하고
Digital Twin PASS/FAIL 결과와 baseline 유지 여부를 기록한다.

전제: Docker ONOS + Mininet 환경, sudo -E python3 으로 실행

실행:
    cd endTOend/
    sudo -E $(which python3) experiments/sec5_3_twin/run.py
"""
from __future__ import annotations

import csv
import json
import sys
import time
from pathlib import Path

_BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_BASE))

import config

TEST_INTENTS = [
    # (id, category, intent)
    ("B1", "block", "block all IPv4 traffic from 10.0.0.1 to 10.0.0.4 on switch 4"),
    ("B2", "block", "block TCP traffic on port 22 destined for 10.0.0.2 on switch 1"),
    ("B3", "block", "block all traffic from 10.0.0.3 to 10.0.0.4 on switch 4"),
    ("F1", "forward", "forward HTTP traffic from port 1 to port 2 on switch 1"),
    ("F2", "forward", "forward ICMP traffic destined for 10.0.0.1 through port 3 on switch 1"),
    ("F3", "forward", "forward TCP traffic on port 80 destined for 10.0.0.3 via port 2 on switch 1"),
]


def run_pipeline(intent: str, skip_deploy: bool = True) -> dict:
    """파이프라인 실행 후 결과 dict 반환"""
    import subprocess
    result = subprocess.run(
        [
            sys.executable, str(_BASE / "pipeline.py"),
            "--intent", intent,
            "--skip-deploy" if skip_deploy else "--no-skip-deploy",
        ],
        capture_output=True, text=True, cwd=str(_BASE),
        timeout=300,
    )
    return {
        "stdout": result.stdout,
        "stderr": result.stderr,
        "returncode": result.returncode,
    }


def main():
    rows = []
    passed = 0

    print("Section 5.3 — Digital Twin 검증")
    print("=" * 60)

    for tid, category, intent in TEST_INTENTS:
        print(f"\n[{tid}] {category.upper()} — {intent}")
        t0 = time.monotonic()

        try:
            result = run_pipeline(intent)
            elapsed = time.monotonic() - t0

            stdout = result["stdout"]
            returncode = result["returncode"]

            # twin 결과 파싱
            if "검증 통과" in stdout or "passed" in stdout:
                twin_status = "passed"
            elif "스킵됨" in stdout or "skipped" in stdout:
                twin_status = "skipped"
            elif "검증 실패" in stdout or "failed" in stdout:
                twin_status = "failed"
            else:
                twin_status = "unknown"

            # 최종 결정
            decision = "APPROVE" if returncode == 0 else (
                "APPROVE_WITHOUT_TWIN" if returncode == 1 else "REJECT"
            )

            ok = twin_status == "passed"
            if ok:
                passed += 1

            print(f"  → twin={twin_status} | decision={decision} | {elapsed:.1f}s")

            rows.append({
                "id": tid,
                "category": category,
                "intent": intent,
                "twin_status": twin_status,
                "decision": decision,
                "elapsed_s": f"{elapsed:.1f}",
                "pass": "1" if ok else "0",
            })

        except Exception as exc:
            elapsed = time.monotonic() - t0
            print(f"  ERROR: {exc}")
            rows.append({
                "id": tid,
                "category": category,
                "intent": intent,
                "twin_status": "error",
                "decision": "ERROR",
                "elapsed_s": f"{elapsed:.1f}",
                "pass": "0",
            })

    print("\n" + "=" * 60)
    print(f"  결과: {passed}/{len(TEST_INTENTS)} PASS")
    print("=" * 60)

    out = Path(__file__).parent / "results" / "twin_results.csv"
    out.parent.mkdir(exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "category", "intent", "twin_status", "decision", "elapsed_s", "pass"])
        writer.writeheader()
        writer.writerows(rows)
    print(f"결과 저장: {out}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    main()
