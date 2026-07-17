# endTOend 평가 실험

논문 **"LLM 기반 SDN 네트워크 인텐트 자동화를 위한 XAI 통합 파이프라인 설계"** (KICS 2026-08-24 제출)의 Section 5 평가 실험 모음.

각 폴더는 논문의 한 섹션에 대응하며, `run.py`를 실행하면 결과가 `results/`에 저장된다.

---

## 실험 목록

| 폴더 | 논문 섹션 | 측정 대상 | 환경 |
|------|----------|----------|------|
| [sec5_1_parsing](sec5_1_parsing/) | 5.1 Intent 파싱 정확도 | slot_accuracy, hallucination_rate | LLM 필요 |
| [sec5_2_conflict](sec5_2_conflict/) | 5.2 충돌 탐지율 | Precision / Recall / F1 | 즉시 실행 가능 |
| [sec5_3_twin](sec5_3_twin/) | 5.3 Digital Twin 검증 | PASS/FAIL (6종 인텐트) | ONOS + Mininet 필요 |
| [sec5_4_xai](sec5_4_xai/) | 5.4 XAI 설명 충실도 | faithfulness score E1~E6 | 즉시 실행 가능 |

---

## 각 실험 상세

---

### sec5_1_parsing — Intent 파싱 정확도

**논문 기여:** C1 (Intent IR), C2 (결정론적 컴파일러)

**목적:**
자연어 인텐트를 LLM이 IntentIR로 변환할 때 얼마나 정확한지 측정한다.
LLM이 정답 없는 필드에 값을 만들어내는 환각(hallucination) 비율도 함께 측정한다.

**데이터셋:**
- `sdn_intent-framework/experiments/e1/data/intents.jsonl` (100케이스)
- 분포: forwarding 42 / security 23 / qos 23 / compound 2 / rejection 10
- 출처: NetIntent 업스트림 50 + 프로젝트 자작 50

**측정 지표:**

| 지표 | 설명 |
|------|------|
| `action` 정확도 | block / forward / qos 분류 정확도 |
| `device_num` 정확도 | 스위치 번호 추출 정확도 (s1~s4) |
| `src_ip` 정확도 | 출발지 IP 추출 정확도 |
| `dst_ip` 정확도 | 목적지 IP 추출 정확도 |
| `ip_proto` 정확도 | 프로토콜 추출 정확도 (tcp/udp/icmp) |
| `dst_port` 정확도 | 목적지 포트 추출 정확도 |
| `hallucination_rate` | gold=None 필드에 LLM이 값을 생성한 비율 |
| `compile_success_rate` | Stage 2 FlowRule 컴파일 성공률 |

**실행:**
```bash
cd endTOend/

# 전체 100케이스 (LLM 호출 ~100회, 수십 분 소요)
python experiments/sec5_1_parsing/run.py

# 빠른 테스트 (10케이스)
python experiments/sec5_1_parsing/run.py --limit 10 --verbose

# RAG 없이 LLM 직접 호출 (비교 baseline)
python experiments/sec5_1_parsing/run.py --no-rag
```

**결과 파일:** `sec5_1_parsing/results/eval_results.csv`

---

### sec5_2_conflict — 정적 검증 충돌 탐지율

**논문 기여:** C3 (Rule-based 정적 검증)

**목적:**
충돌 탐지기(conflict_detector.py)가 5종 충돌 유형을 정확히 탐지하는지 측정한다.
고의로 설계한 레이블 케이스(TP/FP/FN/TN)로 Precision / Recall / F1을 계산한다.

**충돌 유형 5종:**

| 유형 | 설명 |
|------|------|
| Shadowing | 고우선순위 룰이 저우선순위 룰의 match를 완전히 포함 → 하위 룰 도달 불가 |
| Redundancy | match 동일 + action 동일 → 중복 룰 |
| Correlation | 동일 priority + match 겹침 + action 다름 → 비결정적 |
| Imbrication | 동일 priority + match 포함 관계 + action 다름 → 비결정적 |
| Generalization | 포함 관계 + action 동일 → 넓은 쪽이 좁은 쪽을 포함 |

**테스트셋:** `run.py` 내 CONFLICT_CASES (수작업 레이블 11케이스)
- TP 케이스 8개 (유형별 1~2개)
- TN 케이스 3개 (priority 해소, match 비겹침, proto 다름)

**실행:**
```bash
cd endTOend/
python experiments/sec5_2_conflict/run.py
```

**결과 파일:** `sec5_2_conflict/results/conflict_detection.csv`

---

### sec5_3_twin — Digital Twin 검증

**논문 기여:** C4 (Digital Twin 검증 루프)

**목적:**
실제 ONOS + Mininet 환경에서 인텐트별 FlowRule을 배포하고 의도한 트래픽 제어가
동작하는지 검증한다. block 3종 / forward 3종 총 6개 인텐트를 테스트한다.

**테스트 인텐트:**

| ID | 유형 | 인텐트 |
|----|------|--------|
| B1 | block | block all IPv4 traffic from 10.0.0.1 to 10.0.0.4 on switch 4 |
| B2 | block | block TCP traffic on port 22 destined for 10.0.0.2 on switch 1 |
| B3 | block | block all traffic from 10.0.0.3 to 10.0.0.4 on switch 4 |
| F1 | forward | forward HTTP traffic from port 1 to port 2 on switch 1 |
| F2 | forward | forward ICMP traffic destined for 10.0.0.1 through port 3 on switch 1 |
| F3 | forward | forward TCP traffic on port 80 destined for 10.0.0.3 via port 2 on switch 1 |

**전제 조건:**
- Docker ONOS 2.7 실행 중 (`docker run -d --name onos -p 8181:8181 -p 6653:6653 onosproject/onos:2.7`)
- Mininet 설치된 Linux 환경 (WSL2 Ubuntu 권장)
- root 권한 필요

**실행:**
```bash
cd endTOend/
sudo -E $(which python3) experiments/sec5_3_twin/run.py
```

**결과 파일:** `sec5_3_twin/results/twin_results.csv`

---

### sec5_4_xai — XAI 설명 충실도

**논문 기여:** C5 (Evidence-grounded XAI)

**목적:**
XAI 보고서의 각 설명 근거가 실제 스테이지 출력 데이터와 연결되어 있는지 자동으로 검증한다.
6개 시나리오 × 6개 체크 항목 = 36개 기준으로 충실도(faithfulness)를 측정한다.

**충실도 체크 항목 (E1~E6):**

| 항목 | 기준 |
|------|------|
| E1 | `ir_summary`에 action 필드가 포함되어 있는가 |
| E2 | `flowrule_summary`에 deviceId와 priority가 포함되어 있는가 |
| E3 | `static_summary`가 `StaticResult.summary()`와 동일한가 |
| E4 | `twin_summary`가 `twin_result.status`를 반영하는가 |
| E5 | `decision`이 static.passed + twin.status 조합과 일치하는가 |
| E6 | `evidence` 배열이 4개 스테이지(Stage1~4)를 모두 포함하는가 |

**테스트 시나리오:**

| ID | action | static | twin | expected decision |
|----|--------|--------|------|------------------|
| X01 | block | PASS | passed | APPROVE |
| X02 | forward | PASS | passed | APPROVE |
| X03 | block | FAIL | passed | REJECT |
| X04 | forward | PASS | failed | REJECT |
| X05 | block | PASS | skipped | APPROVE_WITHOUT_TWIN |
| X06 | qos | PASS | skipped | APPROVE_WITHOUT_TWIN |

**실행:**
```bash
cd endTOend/
python experiments/sec5_4_xai/run.py
```

**결과 파일:** `sec5_4_xai/results/xai_faithfulness.csv`

---

## 실행 순서 (권장)

```bash
# 1. 즉시 실행 가능한 실험부터
python experiments/sec5_2_conflict/run.py
python experiments/sec5_4_xai/run.py

# 2. LLM 필요 (비용/시간 소요)
python experiments/sec5_1_parsing/run.py --limit 10   # 먼저 소규모 테스트
python experiments/sec5_1_parsing/run.py              # 전체 100케이스

# 3. ONOS + Mininet 환경에서
sudo -E $(which python3) experiments/sec5_3_twin/run.py
```

## 결과 요약 위치

| 실험 | 결과 파일 |
|------|----------|
| sec5_1 | `sec5_1_parsing/results/eval_results.csv` |
| sec5_2 | `sec5_2_conflict/results/conflict_detection.csv` |
| sec5_3 | `sec5_3_twin/results/twin_results.csv` |
| sec5_4 | `sec5_4_xai/results/xai_faithfulness.csv` |
