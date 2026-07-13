# 논문 분석 요약

> papers/ 폴더의 PDF 전체 분석 결과. 각 논문의 우리 연구와의 관련성 중심으로 정리.

---

## 분석 완료 논문 목록 (11개)

| # | 파일명 | 제목 (약칭) | 연도 | 저장 위치 |
|---|--------|-------------|------|-----------|
| 1 | 2607.00292v1.pdf | ResiNet-LLM (토폴로지 생성) | 2026 | ref_llm_network #1 |
| 2 | 2606.28348v1.pdf | Intent-Driven 6G Orchestration (SHACL+LangGraph) | 2026 | ref_sdn_intent #1 |
| 3 | 2606.15709v1.pdf | Water Network DT+LLM+RAG | 2026 | ref_digital_twin #2, ref_rag #2 |
| 4 | 2606.06212v1.pdf | Agentic Config Repair (Batfish+ReAct) | 2026 | ref_xai #2 |
| 5 | symmetry-18-00337.pdf | Safe IoT Network Mgmt (MDE+OCL+RAG) | 2026 | ref_sdn_intent #3 |
| 6 | 2606.01925v2.pdf | QoEReasoner (XAI+RAN Diagnosis) | 2026 | ref_xai #1, ref_llm_network #2 |
| 7 | Int J Network Mgmt...pdf | LLM Network Mgmt Survey (54p) | 2025 | ref_llm_network #5 |
| 8 | Intent-LLM...pdf | Intent-LLM (Intent→Python Code) | 2026 | ref_sdn_intent #2, ref_llm_network #3 |
| 9 | s10922-026-10078-x.pdf | VNF Agent (NDT+RAG+MAD) | 2026 | ref_digital_twin #1, ref_rag #1, ref_llm_network #4 |
| 10 | 2606.10942v1.pdf | Generative Explainability: LLM-Augmented XAI (WiMob 2025) | 2025 | ref_xai #3 |
| 11 | 2602.13672v1.pdf | LEAD-Drift: Explainable Intent Drift Detection (IEEE ICC 2026) | 2026 | ref_xai #4 |
| 12 | 2602.05279v1.pdf | Hallucination-Resistant Security Planning (IEEE NOMS 2026) | 2026 | ref_xai #5 |
| 13 | 2509.22834v1.pdf | LLM + Formal Methods for Optical Network Design (AICCSA 2025) | 2025 | ref_sdn_intent #4 |
| 14 | JAKO201302757805044.pdf | (미분석 - 한국어 논문, 확인 필요) | - | - |
| 15 | sdnhistory.pdf | (SDN 역사 개론 - 배경 지식용) | - | - |

---

## 우리 연구와 가장 관련성 높은 논문 TOP 5

### 1순위: s10922 — VNF 배포 AI 에이전트 (POSTECH 홍원기 교수팀)
- **이유**: NDT(Digital Twin) + RAG + MAD + Self-Healing 루프 → 우리 시스템 전체 구조와 가장 유사
- **차별점 명확**: VNF 배포 vs. FlowRule 정책 생성. XAI 없음 vs. 우리는 XAI 추가
- **활용**: Related Work 핵심 선행 연구, 설계 벤치마크

### 2순위: 2606.28348 — Intent-Driven 6G Orchestration
- **이유**: SHACL 형식 검증 + LangGraph + 그라운딩 환각 방지 → 우리의 Static Validator + RAG 설계에 직접 적용
- **활용**: SHACL 기반 Static Validator 설계 참고, LangGraph 구현 참고

### 3순위: QoEReasoner (2606.01925)
- **이유**: XAI 설명 보고서 구조 (인과 체인 + 대안 + 자연어) 가장 상세히 다룸
- **활용**: 우리 XAI 모듈의 출력 형식 설계 참고, 전문가 평가 지표 참고

### 4순위: Agentic Config Repair (2606.06212)
- **이유**: Batfish 형식 검증 피드백 → LLM 자동 수정 = 우리의 핵심 메커니즘
- **활용**: Static Validator 피드백 루프 설계, CORNETTO 같은 벤치마크 설계 참고

### 5순위: Hong et al. Survey (Int J Network Mgmt)
- **이유**: 우리 연구 필요성의 배경 + "DT로 환각 명령 제거 필요성" 명시
- **활용**: Introduction 동기 부여, Related Work 구조화, 미래 방향 인용

---

## 우리 연구의 차별점 정리 (논문 분석 결과 기반)

| 기존 연구 | 한계 | 우리가 추가하는 것 |
|-----------|------|-------------------|
| Intent-LLM (Provvedi) | 검증 없음, XAI 없음 | Static Validator + DT 검증 + XAI |
| VNF Agent (Nam) | FlowRule 아님, XAI 없음 | FlowRule 정책 생성 특화 + XAI |
| ResiNet-LLM (El Habbouli) | 토폴로지만, 정책 생성 안 함 | 정책(FlowRule) 생성 + 검증 |
| 6G Orchestration (Martins) | 6G 서비스 레벨, XAI 없음 | SDN FlowRule 레벨 + XAI |
| Water DT+RAG (Fasha) | 수도 도메인, XAI 없음 | SDN 도메인 특화 + XAI |
| Survey (Hong) | 서베이만, 구현 없음 | 실제 구현 + 실험 |
| **NetIntent (Hossain)** | **RAG 없음, DT 없음, XAI 없음** | **RAG + Mininet DT + XAI 추가** |

**핵심 차별점**: **"SDN FlowRule 생성 + RAG + Static Validator + Digital Twin 사전 검증 + XAI 설명"의 End-to-End 파이프라인**을 모두 통합한 연구는 없음. NetIntent가 가장 유사하나 RAG/DT/XAI 부재.

---

---

## 2차 수집 논문 (XAI SDN / Intent-based networking LLM 검색)

| 논문 | 핵심 기여 | 우리 연구 활용 |
|------|-----------|----------------|
| 2606.10942 XAI+LLM (WiMob 2025) | SHAP + Mutual Interaction → LLM 자연어 설명, +12.2% usefulness | XAI 모듈 설계, 평가 지표 |
| 2602.13672 LEAD-Drift (ICC 2026) | Intent Drift → 지도학습 + SHAP XAI, 7.3분 조기 탐지 | IBN Assurance 레이어, SHAP 인용 |
| 2602.05279 Hallucination-Resistant (NOMS 2026) | 일관성 검사 + DT 피드백 + ICL 루프, -30% 복구 시간 | 환각 방지 루프 이론적 근거 |
| 2509.22834 LLM+Formal Methods (AICCSA 2025) | CFG 구조 검증 + PDDL 계획 + Optical RAG | Static Validator 설계, 환각 구조적 탐지 |

---

---

## 3차 수집 논문

| 논문 | 핵심 기여 | 우리 연구 활용 |
|------|-----------|----------------|
| NetIntent (Hossain, IEEE OJCOMS 2025) | ⚠️ Intent2Flow-ONOS + FlowConflict-ONOS + 33개 LLM 벤치마크. IBNBench 공개 | **가장 중요한 선행 연구** — IBNBench 데이터셋 평가에 사용, XAI+DT로 차별화 |
| DT + ZTN (IIIT Bangalore, FNWF 2025) | DT + BiLSTM + Q-learning 대역폭 예측, LLM 없음 | DT What-if 시나리오 개념 인용 |
| NIST XAI 4원칙 (NISTIR 8312, 2021) | Explanation / Meaningful / Explanation Accuracy / Knowledge Limits | XAI 모듈 이론 기반, 논문 권위 보강 |

---

## 추가 확인 필요 논문

- `JAKO201302757805044.pdf`: 한국어 논문으로 보임 — 내용 확인 후 관련 ref_ 파일에 추가
- `sdnhistory.pdf`: SDN 역사/개론 — Related Work 배경 설명에 활용 가능

