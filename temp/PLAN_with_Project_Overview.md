# 2026년 7월 14일–8월 24일 연구·구현·실험·논문 작성 통합 계획

## 0. 프로젝트 개요

### 0.1 프로젝트명

**Digital Twin 검증을 활용한 설명가능한 LLM 및 RAG 기반 Intent-Driven SDN 자동화 프레임워크**

영문 제목:

**An Explainable LLM-RAG Framework for Intent-Driven SDN Automation with Digital Twin Validation**

### 0.2 연구 배경

최근 네트워크 운영 분야에서는 Intent-Based Networking(IBN), AIOps, Autonomous Network 및 Zero-Touch Network Management를 중심으로 AI 기반 운영 자동화 연구가 확대되고 있다. 특히 LLM은 운영자의 자연어 요구를 해석하여 네트워크 정책이나 장비 설정으로 변환할 수 있다는 점에서 높은 활용 가능성을 가진다.

그러나 LLM이 생성한 정책을 실제 네트워크에 직접 적용할 경우, 존재하지 않는 장비나 인터페이스를 참조하는 hallucination, 기존 flow rule과의 충돌, 과도하게 넓은 match 조건, 연결성 훼손 및 성능 저하와 같은 문제가 발생할 수 있다. 또한 정책이 생성되거나 거절된 이유가 실제 네트워크 상태 및 검증 결과와 연결되지 않으면, 운영자가 자동화 시스템의 판단을 신뢰하기 어렵다.

따라서 본 프로젝트는 자연어 intent를 단순히 SDN 정책으로 변환하는 데 그치지 않고, 생성된 정책을 정적 검증과 Digital Twin 기반 실행 검증을 통해 사전에 평가하며, 검증 근거를 운영자가 이해할 수 있는 형태로 설명하는 안전한 네트워크 자동화 구조를 연구한다.

### 0.3 연구 목적

본 연구의 목적은 사용자의 자연어 네트워크 운영 intent를 LLM 및 RAG를 통해 controller-neutral Intent IR로 변환하고, 이를 결정론적 방식으로 SDN 정책에 컴파일한 뒤, 실제 배포 전에 Mininet 기반 validation twin에서 안전성과 동작 적합성을 검증하는 프레임워크를 설계·구현하는 것이다.

또한 정적 검증이나 Digital Twin 검증에서 실패한 정책에 대해서는 구조화된 실패 근거를 바탕으로 제한적인 최소 수정 repair loop를 수행하고, 최종적으로 APPROVE, REJECT 또는 HOLD 결정을 생성한다. XAI 설명 계층은 intent 해석, 정책 생성, 검증 결과, 수정 이력 및 최종 결정의 근거를 실제 evidence와 연결하여 제공한다.

### 0.4 핵심 문제 정의

기존 LLM 기반 Intent-Driven SDN 자동화는 자연어 intent translation과 flow rule 생성에 초점을 두는 경우가 많지만, 다음 문제를 충분히 해결하지 못할 수 있다.

1. 자연어의 모호성과 LLM hallucination으로 인해 잘못된 entity 또는 정책이 생성될 수 있다.
2. 문법적으로 올바른 flow rule이라도 기존 정책과 충돌하거나 data-plane behavior를 훼손할 수 있다.
3. 정적 검증만으로는 실제 reachability, isolation, regression 및 장애 상황에서의 동작을 완전히 보장하기 어렵다.
4. 실패 시 정책 전체를 다시 생성하면 기존에 올바른 필드까지 변경되어 새로운 오류가 발생할 수 있다.
5. 자유 형식의 LLM 설명은 실제 telemetry나 verifier 결과와 일치하지 않는 unsupported claim을 포함할 수 있다.

본 연구는 Intent IR, 정적 검증, deterministic compiler, Digital Twin 실행 검증, 최소 수정 repair 및 evidence-grounded XAI를 결합하여 이러한 문제를 완화한다.

### 0.5 연구 범위

본 프로젝트는 1인 개발과 제한된 연구 기간을 고려하여 다음 범위로 제한한다.

**포함 범위**

- 자연어 intent의 controller-neutral Intent IR 변환
- 정적 문서 및 현재 네트워크 상태 기반 retrieval/grounding
- Schema, reference, conflict 및 feasibility 검증
- Intent IR의 deterministic SDN policy 변환
- Mininet 기반 production emulator와 validation twin 분리
- Reachability, isolation, regression, 단일 link failure 및 제한적 QoS 검증
- 실패 evidence 기반 최소 수정 repair loop
- APPROVE / REJECT / HOLD 결정
- Evidence-grounded XAI report
- Forwarding, Security/Isolation 및 제한적 QoS intent

**제외 범위**

- 대규모 물리 네트워크 및 상용 운영망 실증
- Multi-controller 또는 multi-domain 통합
- 5G Core, RAN 및 Kubernetes 통합
- Multi-agent orchestration
- 강화학습 기반 정책 최적화
- LLM fine-tuning 및 지속적 self-learning
- 복수 동시 장애 및 대규모 topology 검증

### 0.6 연구 질문

- **RQ1.** LLM/RAG는 자연어 네트워크 intent를 얼마나 정확하고 일관된 Intent IR로 변환할 수 있는가?
- **RQ2.** 정적 검증은 hallucinated entity, rule conflict 및 실행 불가능한 정책을 얼마나 조기에 차단할 수 있는가?
- **RQ3.** 정적 검증을 통과한 정책이 실제 data-plane behavior에서도 원래 intent를 만족하는가?
- **RQ4.** Digital Twin 기반 사전 검증은 unsafe deployment와 기존 정상 트래픽의 regression을 얼마나 줄일 수 있는가?
- **RQ5.** 실패 evidence를 이용한 최소 수정 repair loop는 전체 재생성 없이 정책 성공률을 개선할 수 있는가?
- **RQ6.** Evidence-grounded XAI report는 자유 형식 설명보다 실제 시스템 판단 근거를 더 충실하게 반영하는가?

### 0.7 제안 시스템 개요

```text
Natural Language Intent
          │
          ▼
   LLM + Retrieval
          │
          ▼
Controller-neutral Intent IR
          │
          ▼
    Static Validator
          │
          ▼
 Deterministic Compiler
          │
          ▼
Digital Twin Active Validation
          │
     ┌────┴────┐
     │         │
   PASS      FAIL / UNCERTAIN
     │         │
     │         ▼
     │   Evidence-based Repair
     │         │
     │    Re-validation
     │
     ▼
APPROVE / REJECT / HOLD
          │
          ▼
 Evidence-grounded XAI Report
          │
          ▼
Production Emulator Deployment
```

### 0.8 예상 연구 기여

1. **Controller-neutral Intent IR 설계**  
   자연어 intent와 controller-specific flow rule 사이에 검증 가능한 중간 표현을 두어 LLM과 SDN 제어 로직의 역할을 분리한다.

2. **정적 검증과 Digital Twin 실행 검증의 결합**  
   문법 및 정책 수준 검증과 실제 data-plane behavior 검증을 단계적으로 결합하여 unsafe policy를 실제 배포 전에 차단한다.

3. **실패 evidence 기반 최소 수정 repair loop**  
   검증 실패 원인을 구조화하고, 정책 전체가 아니라 오류와 직접 관련된 필드만 수정하여 재검증하는 경량 repair 방법을 제안한다.

4. **Evidence-grounded XAI 설명 구조**  
   LLM의 자유 생성 설명이 아니라 intent, retrieved context, flow rule, verifier result 및 repair history에 연결된 설명을 제공한다.

5. **단계별 비교 및 ablation 실험**  
   LLM direct, Intent IR, Static Validator, Digital Twin, Repair 및 XAI를 누적·제거 비교하여 각 구성 요소가 정확성, 안전성, 지연 및 설명 충실도에 미치는 영향을 정량적으로 분석한다.

### 0.9 기대 효과

본 프로젝트를 통해 LLM/RAG, SDN, Network Digital Twin 및 XAI를 하나의 네트워크 운영 자동화 파이프라인으로 통합하는 경험을 확보할 수 있다. 연구 결과는 NetOps/AIOps, SDN/NFV, 클라우드 네트워크 및 자율 네트워크 분야의 취업 포트폴리오로 활용할 수 있으며, 대학원 진학 시 Intent-Based Networking, Safe AI Agent, Network Digital Twin 및 Explainable Network Automation 연구로 확장할 수 있다.

### 0.10 최종 산출물

- 자연어 intent 처리 및 Intent IR 생성 모듈
- Retrieval/state-grounding 모듈
- Static Validator
- Deterministic Policy Compiler
- Production Emulator 및 Validation Twin
- Active Verification 및 Rollback 모듈
- Evidence-based Repair Loop
- APPROVE / REJECT / HOLD Decision Engine
- Evidence-grounded XAI Report Generator
- 실험 데이터셋, 실행 로그, 결과 CSV 및 그래프
- 재현 가능한 Git 저장소
- 제출용 논문과 발표 자료

---

## 1. 계획 전제

- **논문 제출 마감:** 2026년 8월 24일
- **최종 논문 작성·첨삭·제출 전용 기간:** 8월 18일–8월 24일
- **구현 및 본 실험 종료 시점:** 8월 17일
- **개발 인원 가정:** 1인
- **실험 환경:** 저사양 Ubuntu 서버, Mininet, Open vSwitch, ONOS 우선
- **Controller fallback:** 7월 20일까지 ONOS 제어가 안정화되지 않으면 Ryu로 전환
- **LLM:** 외부 API 사용
- **연구 범위:** Forwarding, Security/Isolation, 제한적 QoS
- **Digital Twin 표현:** Mininet 기반 production emulator와 validation twin을 분리한 emulation-based pre-deployment validation 구조

본 연구는 자연어 intent를 바로 네트워크에 반영하지 않고, controller-neutral Intent IR, 정적 검증, Digital Twin 실행 검증, 실패 기반 최소 수정, 근거 기반 설명을 거쳐 최종 배포 여부를 결정하는 안전한 폐루프형 SDN 자동화 프레임워크를 목표로 한다.

---

# 2. 일정 운영 원칙

## 2.1 실험 동결 원칙

- **8월 14일:** 신규 기능 추가 종료
- **8월 15일:** 실험 코드 동결
- **8월 16일:** 전체 실험 결과 동결
- **8월 17일:** 표·그래프·사례 분석 및 논문 초안 완성
- **8월 18일 이후:** 치명적 오류가 아닌 한 신규 기능 추가 및 대규모 재실험 금지

## 2.2 논문 병행 작성 원칙

논문은 마지막 주에 처음 쓰지 않는다.

매일 구현 또는 실험이 끝날 때 다음 자료를 바로 저장한다.

```text
paper/
├── outline.md
├── related_work_matrix.csv
├── method_notes/
├── experiment_protocol/
├── result_tables/
├── figures/
├── case_studies/
├── limitations.md
└── daily_research_log/
```

모든 실험 실행은 다음 메타데이터와 함께 저장한다.

```text
run_id
date
git_commit
model_name
prompt_version
topology_id
intent_id
feature_flags
random_seed
input_intent
generated_ir
static_validation
compiled_policy
twin_test_results
repair_history
final_decision
execution_time
token_usage
```

---

# 3. 8월 17일까지 반드시 완성할 최소 연구 범위

## 3.1 필수 기능

1. 자연어 intent → controller-neutral Intent IR
2. lightweight retrieval 또는 state-grounded prompting
3. Schema, reference, conflict, feasibility 정적 검증
4. Intent IR → deterministic flow rule 변환
5. Production Emulator → Twin 상태 복제
6. Twin 임시 배포 및 rollback
7. Reachability, isolation, regression, 단일 link failure 검증
8. 제한적 QoS 검증
9. 실패 증거 구조화
10. 최대 3회의 최소 수정 repair loop
11. APPROVE / REJECT / HOLD 결정
12. evidence-grounded XAI report

## 3.2 최종 실험 데이터셋 목표

| 유형 | 목표 수 |
|---|---:|
| Forwarding | 15 |
| Security/Isolation | 15 |
| QoS | 10 |
| Conflict/Invalid | 10 |
| Fault/Regression | 10 |
| **합계** | **60** |

## 3.3 Topology 목표

- Topology A: 단일 switch 기반 4-host topology
- Topology B: diamond topology
- Topology C: redundancy가 있는 확장 topology — 일정이 허용하는 경우

## 3.4 비교 시스템

| ID | 구성 |
|---|---|
| B0 | LLM direct 또는 최소 structured prompting |
| B1 | LLM + Intent IR + deterministic compiler |
| B2 | B1 + Static Validator |
| B3 | B2 + Digital Twin active verification |
| B4 | B3 + Repair loop |
| Proposed | B4 + regression/fault validation + APPROVE/REJECT/HOLD + XAI |

## 3.5 핵심 ablation

일정상 다음 네 개를 우선한다.

- Proposed − retrieval
- Proposed − static validation
- Proposed − Digital Twin
- Proposed − repair loop

Fault injection, HOLD, XAI 제거 실험은 시간이 남을 경우 추가한다.

## 3.6 핵심 지표

- Schema Validity Rate
- Intent Slot Accuracy
- Hallucinated Entity Rate
- Static Rejection Precision / Recall
- Flow Installation Success Rate
- Intent Fulfillment Rate
- Regression Rate
- Fault Scenario Pass Rate
- False Approval Rate
- False Rejection Rate
- Repair Success Rate
- Mean Repair Iterations
- End-to-End Latency
- Twin–Production Behavioral Agreement
- Explanation Evidence Coverage
- Unsupported Explanation Claim Rate

---

# 4. 날짜별 통합 계획

## 4.1 7월 14일–7월 20일: 범위 동결, 논문 뼈대, 환경 구축

| 날짜 | 구현·실험 작업 | 논문에 넣을 자료 및 당일 정리 |
|---|---|---|
| **7/14** | 연구 질문, 기여점, 시스템 경계, 제외 범위 확정 | 제목 후보, 문제정의, 연구 질문 RQ1–RQ6, 기여점 3–4개 작성 |
| **7/15** | Git 저장소, Python 프로젝트, 설정 파일, logging 구조 생성 | 논문 전체 목차 작성, 각 절별 핵심 주장 2–3문장 작성 |
| **7/16** | Mininet·OVS·ONOS 설치 및 버전 기록 | Experimental Setup 초안: CPU, RAM, OS, 버전, 네트워크 구성 기록 |
| **7/17** | 단일 topology와 controller 연결 smoke test | SDN testbed 구성 그림 초안, switch/host 목록과 주소표 작성 |
| **7/18** | REST API로 flow 조회·설치·삭제 테스트 | Controller API 표, flow rule 예시, 설치/삭제 로그 저장 |
| **7/19** | Production Emulator와 Twin의 프로세스·port 분리 | “왜 Mininet→Mininet이 가능한가” 방법론 단락, 연구 한계 문장 작성 |
| **7/20** | 환경 Gate 검토, ONOS 유지 또는 Ryu fallback 결정 | 최종 controller 선택 근거, 실패 원인과 대안 기록 |

### 7월 20일 Gate

- Mininet host 간 기본 통신
- Controller에서 switch 인식
- flow 조회·설치·삭제 성공
- Production/Twin 분리 실행 가능
- 논문 Introduction 및 Related Work 골격 작성

---

## 4.2 7월 21일–7월 27일: Intent IR, LLM, retrieval, 초기 번역 실험

| 날짜 | 구현·실험 작업 | 논문에 넣을 자료 및 당일 정리 |
|---|---|---|
| **7/21** | 지원 intent 유형과 Intent IR 필드 정의 | Intent IR 표, 필드 정의, 설계 근거 작성 |
| **7/22** | JSON Schema, typed model, validation error code 설계 | Method의 Intent Representation 절 초안 |
| **7/23** | 외부 LLM API adapter, timeout, retry, structured output | 사용 모델, temperature, token limit, API 설정표 작성 |
| **7/24** | prompt template v1, few-shot 예제 구성 | Prompt template와 예제 intent를 부록용으로 정리 |
| **7/25** | lightweight retrieval 구현 | RAG/retrieval 구성과 검색 근거 저장 형식 작성 |
| **7/26** | topology·host·flow state를 prompt context에 추가 | static document grounding과 state grounding 차이 서술 |
| **7/27** | 자연어→IR 초기 실험 20–30건 실행 | B0/B1 초기 결과표: schema validity, slot accuracy, hallucinated entity 사례 |

### 수집 데이터

- 입력 intent
- LLM raw output
- structured IR
- parsing 실패 유형
- 존재하지 않는 host/switch/port 생성 여부
- API latency와 token usage
- retrieval 적용 전후 차이

### 7월 27일 Gate

- 자연어 intent가 schema-valid IR로 변환
- 최소 20개 초기 사례 결과 확보
- Intent Representation 및 LLM Pipeline 절 초안 완성

---

## 4.3 7월 28일–8월 3일: Static Validator, compiler, 정적 benchmark

| 날짜 | 구현·실험 작업 | 논문에 넣을 자료 및 당일 정리 |
|---|---|---|
| **7/28** | Schema Validator 구현 | validator 계층 그림 및 오류 taxonomy 작성 |
| **7/29** | host/IP/switch/port Reference Validator 구현 | 존재하지 않는 entity 탐지 사례 정리 |
| **7/30** | overlap, allow/drop, shadowing, priority conflict 구현 | conflict 유형 표와 예시 flow pair 작성 |
| **7/31** | path, queue, bandwidth feasibility 규칙 구현 | 지원 가능 범위와 Knowledge Limits 단락 작성 |
| **8/1** | IR→controller-neutral policy compiler 구현 | LLM과 deterministic compiler 역할 분리 근거 작성 |
| **8/2** | controller-specific flow compiler 및 rollback 구현 | 생성 rule 예시, transaction/rollback 절차 작성 |
| **8/3** | 정적 benchmark 40–50건 실행 | B1/B2 결과표, 정적 validator precision/recall, 대표 실패 사례 3개 정리 |

### 수집 데이터

- 오류 유형별 TP, FP, TN, FN
- Static Validator 처리 시간
- LLM direct 생성 대비 deterministic compiler의 syntax/install 성공률
- 정적 단계에서 차단된 정책 수
- Twin 실행을 절약한 비율

### 8월 3일 Gate

- Schema, reference, conflict, feasibility 검사 동작
- 동일 IR에서 deterministic output 생성
- 정적 benchmark 표와 사례 분석 초안 완성

---

## 4.4 8월 4일–8월 10일: Digital Twin, active verification, behavior benchmark

| 날짜 | 구현·실험 작업 | 논문에 넣을 자료 및 당일 정리 |
|---|---|---|
| **8/4** | Production snapshot schema: topology, host, link, flow | DT state model 표와 synchronization 범위 작성 |
| **8/5** | snapshot 수집 및 저장 구현 | Production–Twin state mapping 표 작성 |
| **8/6** | snapshot 기반 Twin 생성·초기화 | Digital Twin 구축 절과 전체 architecture 그림 갱신 |
| **8/7** | 후보 정책 임시 설치·삭제·rollback | pre-deployment safety gate 시퀀스 다이어그램 작성 |
| **8/8** | reachability, isolation, port/protocol test 자동화 | Positive/negative test oracle 표 작성 |
| **8/9** | baseline behavior capture 및 regression test | overbroad rule 사례, 기존 정상 flow 훼손 사례 정리 |
| **8/10** | 단일 link failure, 제한적 QoS, Twin–Production 비교 | B2/B3 결과표, false approval, regression, behavioral agreement 결과 작성 |

### 수집 데이터

- 정책 적용 전 baseline matrix
- 정책 적용 후 expected/observed behavior
- ping, curl, nc, iperf 결과
- controller flow table
- rollback 성공 여부
- link failure 전후 packet loss와 recovery time
- Twin 판단과 Production Emulator 결과의 일치 여부

### 핵심 논문용 사례

1. **정적 benchmark는 성공하지만 실제 동작은 실패하는 정책**
2. **문자열 또는 rule 구조는 다르지만 behavior는 올바른 정책**
3. **요청한 트래픽은 차단하지만 비대상 트래픽까지 차단하는 overbroad policy**
4. **Twin이 위험 정책을 Production 적용 전에 차단한 사례**

### 8월 10일 Gate

- Twin 임시 배포와 rollback 성공
- Reachability, isolation, regression, link failure 자동화
- Behavior-aware benchmark 결과 확보

---

## 4.5 8월 11일–8월 14일: Repair, XAI, 최종 기능 완성

| 날짜 | 구현·실험 작업 | 논문에 넣을 자료 및 당일 정리 |
|---|---|---|
| **8/11** | 실패 결과 evidence normalization | failure evidence JSON 예시와 오류 원인 taxonomy 작성 |
| **8/12** | JSON Patch 또는 field-local repair 구현 | 전체 재생성 대비 최소 수정의 설계 근거 작성 |
| **8/13** | 최대 3회 repair→re-validation loop | repair iteration 사례와 상태 전이 그림 작성 |
| **8/14** | APPROVE/REJECT/HOLD와 XAI report 통합, 신규 기능 종료 | NIST 4원칙과 시스템 mapping 표, XAI report 예시 작성 |

### 수집 데이터

- 첫 시도 성공 여부
- repair 성공 여부
- 반복 횟수
- 수정 필드 수
- 신규 regression 발생 여부
- repair 전후 rule diff
- 설명 문장과 evidence ID 연결
- unsupported claim 여부
- APPROVE/REJECT/HOLD 분포

### 8월 14일 Gate

- 최소 3개 오류 유형 자동 수정
- repair 후 전체 regression 재검사
- evidence-grounded report 생성
- 신규 기능 추가 종료

---

## 4.6 8월 15일–8월 17일: 전체 실험, 결과 동결, 논문 초안 완성

| 날짜 | 구현·실험 작업 | 논문에 넣을 자료 및 당일 정리 |
|---|---|---|
| **8/15** | 코드 동결, 60개 최종 dataset 확정, 전체 실험 dry run | Experiment Protocol 최종본, dataset 통계표 작성 |
| **8/16** | B0–Proposed 및 핵심 ablation 전체 실행 | 모든 정량 결과 CSV, 평균·분산, 실패 사례, 그래프 원본 저장 |
| **8/17** | 결과 검산, 표·그래프 생성, 치명적 오류만 수정 | Results, Discussion, Limitations 작성 후 논문 전체 초안 완성 |

### 8월 16일까지 동결할 결과물

- Table 1: 선행연구 비교
- Table 2: 시스템 구성 및 ablation
- Table 3: dataset 및 topology 통계
- Table 4: intent translation 성능
- Table 5: static validation 성능
- Table 6: Digital Twin behavior 검증
- Table 7: repair 및 regression
- Table 8: end-to-end 성능과 latency
- Figure 1: 전체 architecture
- Figure 2: intent-to-deployment sequence
- Figure 3: Production–Twin 구성
- Figure 4: 누적 구성별 성능
- Figure 5: false approval/regression 비교
- Figure 6: repair iteration 또는 사례 분석
- Figure 7: XAI report 예시

### 8월 17일 Gate

- 본문 전체 초안
- 모든 표·그림 번호 확정
- 초록과 결론을 제외한 본문 90% 이상 완성
- 결과를 다시 생성할 수 있는 실험 명령과 commit 기록

---

## 4.7 8월 18일–8월 24일: 논문 작성·첨삭·제출 전용 기간

| 날짜 | 논문 작업 | 완료 기준 |
|---|---|---|
| **8/18** | Introduction, Problem Statement, Contributions 전면 수정 | 연구 gap과 핵심 주장이 한 문단에서 명확히 연결됨 |
| **8/19** | Related Work와 비교표 정리 | NetIntent, formal validation, NDT repair, XAI와 차별점 명확화 |
| **8/20** | System Design/Methodology 정밀 첨삭 | 모든 module 입력·출력·알고리즘·결정 규칙 명시 |
| **8/21** | Experimental Setup와 Results 정리 | 표·그림이 본문 주장과 직접 연결되고 중복 설명 제거 |
| **8/22** | Discussion, Limitations, Threats to Validity 작성 | Mininet→Mininet, 단일 controller, 소규모 topology 한계 명시 |
| **8/23** | 초록, 결론, 제목, 문법, 인용, 형식, 페이지 제한 최종 점검 | PDF 최종 후보 생성, reference와 figure/table cross-reference 검수 |
| **8/24** | 최종 PDF 검수 및 제출 | 제출 파일, supplementary 자료, 소스 archive 보관 |

---

# 5. 논문 절별 완성 시점

| 논문 절 | 1차 초안 | 최종 수정 |
|---|---:|---:|
| Introduction | 7/20 | 8/18 |
| Related Work | 7/27 | 8/19 |
| Problem Formulation | 7/27 | 8/18 |
| System Architecture | 8/6 | 8/20 |
| Intent IR / Static Validation | 8/3 | 8/20 |
| Digital Twin Verification | 8/10 | 8/20 |
| Repair / XAI | 8/14 | 8/20 |
| Experimental Setup | 8/15 | 8/21 |
| Results | 8/17 | 8/21 |
| Discussion / Limitations | 8/17 | 8/22 |
| Abstract / Conclusion | 8/17 | 8/23 |
| Final formatting | - | 8/23–8/24 |

---

# 6. 연구 질문과 결과 연결

## RQ1. 자연어 intent를 얼마나 정확히 구조화하는가?

비교:

- B0: LLM only
- B1: LLM + Intent IR
- Retrieval ablation

자료:

- Schema validity
- Slot accuracy
- Hallucinated entity rate
- representative parsing failures

## RQ2. 정적 검증은 잘못된 정책을 얼마나 조기에 차단하는가?

비교:

- B1 vs B2
- Proposed − static validation

자료:

- precision/recall
- rejected policy counts
- saved Twin executions
- validation overhead

## RQ3. 정적 정확도가 실제 data-plane behavior를 보장하는가?

비교:

- syntax/static pass
- Twin behavior pass
- Production Emulator behavior pass

자료:

- static-pass/dynamic-fail 사례
- static-mismatch/behavior-pass 사례
- behavioral agreement

## RQ4. Digital Twin은 unsafe deployment를 얼마나 줄이는가?

비교:

- B2 vs B3
- Proposed − Digital Twin

자료:

- false approval
- false rejection
- unsafe policy blocking
- regression detection

## RQ5. 실패 기반 repair가 정책 성공률과 안전성을 개선하는가?

비교:

- B3 vs B4
- Proposed − repair

자료:

- repair success
- mean iterations
- new regression rate
- time to valid policy

## RQ6. 설명은 실제 시스템 근거와 일치하는가?

비교:

- free-form explanation
- evidence-grounded explanation

자료:

- evidence coverage
- unsupported claim rate
- operator/developer report examples
- APPROVE/REJECT/HOLD reasoning

---

# 7. 일정 지연 시 축소 순서

## 반드시 유지

1. Intent IR
2. Static Validator
3. deterministic compiler
4. Digital Twin
5. Reachability, isolation, regression
6. APPROVE / REJECT
7. 실행 기록
8. 최소한의 XAI report

## 축소 가능

1. QoS intent 10개 → 5개
2. Topology C 제거
3. Path verification 제거
4. repair 오류 유형 7개 → 3개
5. HOLD를 단순 규칙 기반으로 축소
6. XAI 사용자 평가 제거
7. 실험 반복 횟수 축소

## 가장 먼저 제외

1. 다중 controller
2. 대시보드
3. vector DB
4. multi-agent
5. 복수 link failure
6. 자동 Twin calibration
7. 물리 장비 연동

---

# 8. 최종 제출 전 체크리스트

## 코드 및 실험

- [ ] 실험 commit 고정
- [ ] 모든 표·그래프가 원본 CSV에서 재생성 가능
- [ ] `run_id`와 논문 사례가 연결됨
- [ ] 실패한 실험도 삭제하지 않고 기록
- [ ] API model/version과 prompt version 기록
- [ ] Production과 Twin 설정 차이 명시
- [ ] rollback 및 cleanup 검증

## 논문

- [ ] 문제정의와 기여점이 초록·서론·결론에서 일관됨
- [ ] NetIntent 대비 차별점이 translation 성능이 아니라 behavior-aware safety validation으로 명확함
- [ ] Mininet을 실제 physical network로 과장하지 않음
- [ ] emulated production network와 validation twin으로 정의
- [ ] 실험 결과가 없는 주장을 삭제
- [ ] 한계와 future work 명시
- [ ] 모든 표·그림이 본문에서 해석됨
- [ ] 참고문헌 형식과 인용 누락 확인
- [ ] 페이지 수와 제출 양식 확인
- [ ] 최종 PDF에서 글꼴, 수식, 그림 해상도 점검

---

# 9. 최종 완료 기준

8월 24일 제출 가능한 상태는 다음 조건을 충족해야 한다.

- 자연어 intent가 controller-neutral IR로 변환된다.
- topology에 없는 entity와 conflict가 탐지된다.
- deterministic compiler가 flow rule을 생성한다.
- 후보 정책이 Twin에서 먼저 검증된다.
- reachability, isolation, regression, link failure 검증이 자동 수행된다.
- 실패 결과가 구조화된 evidence로 저장된다.
- 제한된 오류에 대해 최소 수정과 재검증이 가능하다.
- 최종 결정이 APPROVE, REJECT 또는 HOLD로 기록된다.
- 설명이 실제 intent, rule, verifier result, repair history에 연결된다.
- B0부터 Proposed까지 동일 dataset에서 비교할 수 있다.
- 구현, 실험, 결과, 한계를 포함한 논문이 제출 형식으로 완성된다.

이 계획의 핵심은 8월 17일까지 연구 결과를 동결하고, 8월 18일부터 8월 24일까지는 논문의 논리·표현·형식·재현성만 다듬는 것이다.
