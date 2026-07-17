"""
sec5_1_parsing/run.py — 논문 Section 5.1: Intent 파싱 정확도 평가

측정 지표:
  - slot_accuracy  : action / device / src_ip / dst_ip / ip_proto / dst_port 정확도
  - hallucination_rate : gold=None 필드에 LLM이 값을 생성한 비율
  - compile_success_rate : Stage 2 CompileError 없이 FlowRule 생성 성공률

실행:
    cd endTOend/
    python experiments/sec5_1_parsing/run.py                  # 전체 100케이스
    python experiments/sec5_1_parsing/run.py --limit 10       # 빠른 테스트
    python experiments/sec5_1_parsing/run.py --no-rag         # RAG 없이 LLM 직접
"""
import subprocess
import sys
from pathlib import Path

_BASE = Path(__file__).resolve().parents[2]  # endTOend/
_OUT = Path(__file__).parent / "results" / "eval_results.csv"

args = sys.argv[1:]

subprocess.run(
    [sys.executable, str(_BASE / "evaluate.py"), "--output", str(_OUT)] + args,
    cwd=str(_BASE),
)
