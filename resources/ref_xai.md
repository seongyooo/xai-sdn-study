# XAI (Explainable AI) 관련 논문

---

## Paper 1

**제목:** QoEReasoner: An Agentic Reasoning Framework for Automated and Explainable QoE Diagnosis in RANs
**저자:** Qizhe Li, Haolong Chen, Shan Dai, Zhuo Li, Zhiwei Hu, Xuan Li, Guangxu Zhu, Qingjiang Shi
**출처 (학회/저널):** arXiv:2606.01925v2 [cs.NI]
**연도:** 2026
**링크:** https://arxiv.org/abs/2606.01925

**요약:**
RAN(Radio Access Network)에서 QoE 저하 원인을 자동으로 진단하고 설명하는 Agentic LLM 시스템. 전통적 ML의 블랙박스 한계와 LLM의 수치 분석 실패/환각 문제를 모두 극복하기 위해 결정론적 KPI 도구 + 프로토콜 인식 Knowledge Base + 전문가 사례 Historical Bank를 결합한 폐쇄 루프 추론 프레임워크.

**핵심 내용:**
- **XAI 설계 패턴**:
  - LLM이 내부적으로 추론한 과정(인과 체인)을 외부에 명시적으로 출력
  - KPI 이상 → 교차 계층 전파 경로 → 루트 원인 순으로 연결하는 자연어 설명 생성
  - 최종 진단 + 최상위 결함 체인 + 대안 가설 + KPI 관찰-추론 연결 → "Expert-grade 보고서"

- **4요소 아키텍처**:
  1. 결정론적 KPI 도구 (수치 분석 담당, LLM 수치 처리 약점 보완)
  2. Knowledge Base (KB): 프로토콜 기반 결함 전파 경로 그래프 — 인과 제약 강제
  3. Historical Bank (HB): 전문가 검증 과거 사례 — 가설 공간에 분포 편향(prior) 주입
  4. Stateful Central Planner: 이상탐지 → 인과추적 → 루트원인국소화 폐쇄 루프 조율

- **전문가 평가 지표 (5점 Likert)**:
  - Correctness (Co): 진단 결과 정확성
  - Evidence Grounding (EG): KPI 데이터와 결론 연결 강도
  - Knowledge Grounding (KG): 도메인 지식 활용도
  - Interpretability (In): 설명 이해 용이성 ← 가장 높은 점수

- **주목할 비교 분석** (Table 1):
  - 규칙 기반: R1(수치인식)△, R2(인과설명)✗, R3(교차태스크추론)✗
  - DL: R1✓, R2✗, R3✗
  - 일반 LLM: R1✗, R2△, R3△
  - QoEReasoner: R1✓, R2✓, R3✓

- **성능**: 베이스라인 대비 18-40% 정확도 향상, 진단 시간 30분→3분, 비용 $0.02/세션

**내 연구와의 관련성:**
- **설명 보고서 구조 직접 참고**: 진단 결과 + 인과 체인 + 대안 + 자연어 설명의 계층적 XAI 출력 구조를 우리 FlowRule 설명 모듈에 적용 가능
- **KB+HB = 우리의 RAG**: Knowledge Base(도메인 규칙)와 Historical Bank(과거 사례)의 이중 구조는 우리의 RAG 설계(규칙 문서 + 과거 정책 예시)와 동일한 패턴 → 이 논문으로 설계 타당성 뒷받침
- **Interpretability 지표**: 우리 논문의 XAI 평가에서 Interpretability를 핵심 지표로 삼는 근거로 인용
- **Table 1 비교 프레임**: 우리 논문 Introduction에서 "기존 ML/DL/LLM의 한계 → 우리 시스템의 필요성" 논증에 동일한 비교 프레임 활용 가능

---

## Paper 2

**제목:** Evaluating Agentic Configuration Repair for Computer Networks
**저자:** Arda Asadli, Thomas Holterbach, Laurent Vanbever (ETH Zurich)
**출처 (학회/저널):** ICML 2026 (Workshop on Machine Learning for Networking)
**연도:** 2026
**링크:** https://arxiv.org/abs/2606.06212

**요약:**
네트워크 설정 오류 자동 수정을 위한 ReAct 스타일 Agentic 시스템. 동적 컨텍스트 검색 + 반복적 search-and-replace 편집 + **Batfish 형식 검증 피드백**을 통합. CORNETTO 벤치마크(231개 시나리오, 27개 결함 유형)에서 평가. Agentic 방식이 단일 호출 대비 수정률 +12%, 회귀율 -17%.

**핵심 내용:**
- **ReAct 에이전트 설계**:
  1. 동적 컨텍스트 검색: 설정 파일 + 토폴로지 정보 선택적 로딩
  2. 반복 search-and-replace: 파일 수정 → 검증 → 재수정 루프
  3. **Batfish 검증 피드백**: 형식 검증 도구(Batfish)의 오류 메시지를 LLM에 피드백 → 자동 수정 방향 유도

- **CORNETTO 벤치마크**: 231개 시나리오 × 27개 결함 유형. 오류 있는 설정 입력 → 올바른 설정 출력
- **XAI/설명 측면**: Batfish 검증 오류 메시지가 명시적 피드백으로 작용 → 왜 수정이 필요한지 추적 가능
- **오픈 모델 효과**: 오픈 소스 모델이 Agentic 스캐폴딩으로 7배 성능 향상
- **한계**: 복잡한 다중 결함 시나리오에서 성능 저하

**내 연구와의 관련성:**
- **Batfish = 우리의 Static Validator**: 형식 검증 도구 피드백을 LLM 재생성에 활용하는 패턴이 우리 설계와 동일. 우리는 Batfish 대신 ONOS 기반 커스텀 Static Validator 사용
- **검증 피드백 루프**: 검증 실패 → 오류 메시지 → LLM 재입력 → 재생성 패턴은 우리 파이프라인 핵심 메커니즘
- **CORNETTO 같은 벤치마크 부재**: 우리도 평가 벤치마크를 직접 설계해야 함 → 이 논문의 벤치마크 설계 방식 참고
- **Agentic 스캐폴딩 효과**: +12% 개선 수치는 우리 논문의 Agentic 파이프라인 도입 정당성 강화에 인용 가능

---

## Paper 3

**제목:** Generative Explainability for Next-Generation Networks: LLM-Augmented XAI with Mutual Feature Interactions
**저자:** Kiarash Rezaei, Omran Ayoub, Sebastian Troia, Francesco Lelli, Paolo Monti, Carlos Natalino
**출처 (학회/저널):** IEEE WiMob 2025 (DOI: 10.1109/WiMob66857.2025.11257542)
**연도:** 2025
**링크:** https://arxiv.org/abs/2606.10942

**요약:**
기존 SHAP 기반 XAI는 비전문가에게 기술적 수치만 출력해 실행 가능한 인사이트로 변환이 어렵다는 문제를 해결. **SHAP 특성 중요도 + 상호작용 피처(Mutual Feature Interactions)**를 결합한 구조화된 프롬프트로 중간 규모 LLM을 구동해 자연어 설명 생성. 광학 네트워크 QoT 추정 케이스 스터디.

**핵심 내용:**
- **XAI 파이프라인**:
  1. SHAP feature influence values 계산
  2. Mutual Feature Interaction values 추가 계산 (피처 쌍 간 상호작용 효과)
  3. 두 정보를 결합한 구조화된 프롬프트 → LLM 입력
  4. 자연어 설명 생성 (비전문가 이해 가능)

- **인간 평가 지표**: Usefulness (실행 가능성), Scope (포괄성), Correctness (정확성)
- **결과**: 기존 plain SHAP 대비 Usefulness +12.2%, Scope +6.2%, Correctness 97.5%
- **코드 공개**: https://github.com/kiarashRezaei/llm-for-xai-qotEstimation

**내 연구와의 관련성:**
- **XAI 모듈 설계 직접 참고**: SHAP → LLM 자연어 변환 파이프라인을 FlowRule XAI 모듈에 적용 가능. "왜 이 FlowRule이 생성됐는가?"를 SHAP 분석 후 LLM으로 자연어화
- **Mutual Feature Interaction**: 피처 간 상호작용 분석 → FlowRule 규칙 충돌/의존성 설명에 활용 가능
- **평가 지표**: Usefulness/Scope/Correctness 인간 평가 프레임워크를 우리 논문 XAI 평가 섹션에 적용
- **차별화**: 이 논문은 광학 네트워크 리소스 할당 XAI, 우리는 SDN FlowRule 정책 생성 XAI

---

## Paper 4

**제목:** LEAD-Drift: Real-time and Explainable Intent Drift Detection by Learning a Data-Driven Risk Score
**저자:** Md. Kamrul Hossain, Walid Aljoby (King Fahd University of Petroleum and Minerals)
**출처 (학회/저널):** IEEE ICC 2026
**연도:** 2026
**링크:** https://arxiv.org/abs/2602.13672

**요약:**
IBN에서 인텐트 드리프트(네트워크 상태가 의도한 목표에서 점진적으로 이탈)를 실시간 탐지 + **SHAP 기반 설명** 프레임워크 **LEAD-Drift**. 고정 수평선 레이블링으로 미래 위험 점수 예측 → EMA 평활화 → 통계 임계값 → 알림. 알림 발생 시 SHAP으로 루트 원인 KPI 식별.

**핵심 내용:**
- **핵심 아이디어**: Intent Drift 탐지를 지도학습 문제로 재정의 (현재 상태 → 미래 H분 내 장애 발생 여부)
- **경량 MLP** → raw risk score → EMA 평활화 → 통계 임계값 → 실시간 알림
- **SHAP 기반 XAI**: 알림 발생 시 각 KPI(cpu_pct, ram_pct, serv_resp 등) SHAP 기여도 → "왜 위험한가?" 운영자에게 설명
- **Multi-Horizon**: H₁ < H₂ < ... < Hₙ 수평선별 모델 → 동적 time-to-failure 추정 (카운트다운)
- **결과**: 리드 타임 +17.8% (7.3분 조기 감지), 알림 노이즈 -80.2%

**내 연구와의 관련성:**
- **IBN Assurance 레이어**: 우리 파이프라인의 FlowRule 배포 이후 단계로 인텐트 준수 모니터링 추가 → End-to-End 완성도 향상
- **SHAP + 네트워킹 XAI 선행 사례**: 우리 XAI 모듈의 SHAP 기반 설명 설계에 직접 인용 가능
- **Intent Drift 개념 활용**: "FlowRule 배포 후에도 인텐트 준수 지속 검증 필요" 논증에 인용
- **평가 지표**: Lead Time + Alert Noise 지표를 DT 검증 평가에 응용 가능

---

## Paper 5

**제목:** Hallucination-Resistant Security Planning with a Large Language Model
**저자:** Kim Hammar, Tansu Alpcan, Emil C. Lupu (Univ. Melbourne + Imperial College London)
**출처 (학회/저널):** IEEE/IFIP NOMS 2026
**연도:** 2026
**링크:** https://arxiv.org/abs/2602.05279

**요약:**
LLM 환각을 이론적으로 제어 가능한 보안 계획 프레임워크. 일관성 검증 + Digital Twin 평가 + ICL 반복 정제 루프. Conformal abstention으로 일관성 임계값을 조정해 환각 위험을 수학적으로 제어. 4개 공개 데이터셋에서 frontier LLM 대비 복구 시간 최대 30% 단축.

**핵심 내용:**
- **반복 검증 루프**:
  1. LLM → 후보 행동 생성
  2. Lookahead 예측과의 일관성 검사
  3. 일관성 낮으면 → **Conformal Abstention** (행동 거부) → Digital Twin에서 외부 피드백
  4. 피드백 컨텍스트 통합 → **ICL**로 후보 재생성 → 반복

- **이론적 기여**: 일관성 임계값 조정으로 환각 위험 수준 제어 가능 수학적 증명. ICL 후회(regret) 상한 수립
- **결과**: OpenAI O3 대비 복구 시간 최대 -30%, 4개 데이터셋 검증
- **Ablation**: lookahead / DT 피드백 / ICL 각 구성요소 기여 독립 검증

**내 연구와의 관련성:**
- **환각 방지 루프 = 우리 파이프라인 핵심**: 생성 → 일관성 검사 → DT 검증 → ICL 재생성 = 우리의 FlowRule 생성 → Static Validator → DT 검증 → 재생성 흐름과 동일 구조
- **Conformal Abstention**: 검증 실패 시 거부 + DT 피드백 수집 = 우리 DT 오류 로그 피드백 메커니즘과 동일
- **이론적 보장**: 환각 위험의 수학적 제어 가능성 → 우리 논문의 "안전성" 주장에 이론적 근거
- **Related Work 차별화**: 보안 사건 대응 vs. 우리는 SDN 정책 생성 — 동일 패턴을 다른 도메인에 적용

---
