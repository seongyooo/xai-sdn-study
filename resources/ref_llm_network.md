# LLM for Network Automation 관련 논문

---

## Paper 1

**제목:** An LLM-Based Framework for Intent-Driven Network Topology Design
**저자:** Kholoud El Habbouli, Fen Zhou, Stéphane Huet
**출처 (학회/저널):** arXiv:2607.00292v1 [cs.NI]
**연도:** 2026
**링크:** https://arxiv.org/abs/2607.00292

**요약:**
자연어 요구사항으로부터 배포 가능한 복원력 있는 네트워크 토폴로지를 생성하는 LLM 기반 프레임워크 **ResiNet-LLM**을 제안. 계층적 모델링과 제약 조건 검증을 결합한 파이프라인을 통해 구조적으로 유효하고 제약 조건을 만족하는 토폴로지를 생성하며, 5개 LLM(Gemini 2.5 Flash, GPT-4o, Mistral-Small-24B, Qwen3-32B, DeepSeek-R1-32B)을 4개 시나리오에서 비교 평가.

**핵심 내용:**
- **ResiNet-LLM 파이프라인**: LangChain 기반으로 4단계 구성
  1. **Stateful Layer-wise Generation**: Core → Distribution → Access → Endpoint 순으로 계층별 순차 생성. 이전 계층의 노드/인터페이스 정보를 다음 계층에 전파
  2. **Structured Reasoning**: LLM에 Senior Network Architect 역할 부여 → 후보 토폴로지 3개 생성 → 단일 장애점 최소화 기준으로 선택 → 단일 링크/장치 장애 시뮬레이션 검증
  3. **Schema Validation (Pydantic)**: 생성된 JSON 출력의 구조적 유효성 검사
  4. **Pydantic Error Injection**: 오류 발생 시 에러 메시지를 LLM에 재입력하여 수정 재생성

- **평가 지표**:
  - Node F1 / Edge F1: 생성 토폴로지와 레퍼런스 토폴로지 간 구조적 유사도
  - Server Connectivity (SC): 장애 시 클라이언트 → 주 서버 연결 유지율
  - Content Connectivity (CC): 장애 시 클라이언트 → 주/백업 서버 중 하나 연결 유지율

- **실험 결과**:
  - Gemini 2.5 Flash가 가장 안정적 (5/5 Valid, SC 50%, CC 100%)
  - GPT-4o가 그 다음 (Node F1 1.00, Edge F1 0.89)
  - Mistral, DeepSeek은 연결 실패 비율 높음
  - 네트워크 규모가 커질수록(Scenario 4: 173 nodes) 모든 모델 성능 급락

- **한계**: 토폴로지 설계에만 집중, FlowRule/정책 생성은 다루지 않음. 대규모 네트워크(173 노드)에서 확장성 문제 존재

**내 연구와의 관련성:**
- **Related Work로 활용 가능**: 기존 연구(NetConfEval, S-Witch)는 토폴로지를 입력으로 가정하지만, 이 논문은 토폴로지 자체를 생성 — 우리 연구는 토폴로지가 주어진 상태에서 FlowRule 정책 생성 + 검증 + 설명에 집중하므로 상호 보완적
- **파이프라인 설계 참고**: Stateful Layer-wise Generation의 계층적 생성 방식과 Pydantic 기반 구조 검증은 우리의 Static Validator 설계에 아이디어를 줄 수 있음
- **LangChain 활용**: 동일하게 LangChain 기반 파이프라인 구성 가능
- **평가 방법 참고**: SC/CC 지표는 우리 연구의 네트워크 안전성 평가 지표 설계에 참고 가능

---

## Paper 2

**제목:** QoEReasoner: An Agentic Reasoning Framework for Automated and Explainable QoE Diagnosis in RANs
**저자:** Qizhe Li, Haolong Chen, Shan Dai, Zhuo Li, Zhiwei Hu, Xuan Li, Guangxu Zhu, Qingjiang Shi
**출처 (학회/저널):** arXiv:2606.01925v2 [cs.NI]
**연도:** 2026
**링크:** https://arxiv.org/abs/2606.01925

**요약:**
Radio Access Network(RAN)에서 QoE 저하를 자동으로 진단하고 설명하는 Agentic LLM 프레임워크 **QoEReasoner**를 제안. LLM의 수치 분석 한계와 프로토콜 위반 오류를 극복하기 위해 결정론적 도구 + 도메인 지식 KB + 전문가 사례 HB를 결합. 30분 전문가 분석 → 3분으로 단축.

**핵심 내용:**
- **4가지 핵심 구성요소**:
  1. **결정론적 KPI 도구**: 수치 시계열 데이터를 구조화된 증거로 변환 (LLM의 수치 분석 한계 보완)
  2. **Knowledge Base (KB)**: 도메인 특화 프로토콜-인식 결함 전파 경로 제약 — 프로토콜 위반 인과 관계 생성 방지
  3. **Historical Bank (HB)**: 전문가 검증 과거 사례 — 가설 생성 방향성 제공
  4. **Stateful Central Planner**: 이상 탐지 → 인과 추적 → 루트 원인 국소화의 폐쇄 루프 조율

- **XAI 특성**: 자연어 설명 + KPI 이상 → 전파 경로 연결 + 대안 가설 제시 → Expert-grade 진단 보고서
- **평가 결과**: 기존 베이스라인 대비 정확도 18-40% 향상, 진단 비용 $0.02/세션
- **전문가 평가**: Correctness, Evidence Grounding, Knowledge Grounding, Interpretability 모두 5점 만점 4점 이상

**내 연구와의 관련성:**
- **XAI 관점**: 이 논문의 "설명 가능한 진단 보고서" 구조는 우리 연구의 FlowRule XAI 설명 모듈 설계에 직접 참고 가능 (특히 KPI→전파경로→루트원인 연결 방식)
- **KB + HB = RAG 구조**: Knowledge Base + Historical Bank 조합은 우리의 RAG 설계(도메인 지식 + 과거 사례)와 동일한 패턴
- **Agentic 파이프라인**: Stateful Central Planner 설계는 우리의 LangGraph 기반 에이전트 파이프라인에 참고
- **평가 지표**: Expert 주관 평가(Likert scale) + 정량 지표 병행 방식은 우리 논문 평가 설계에 참고

---

## Paper 3

**제목:** Intent-LLM: A Framework for Automated Network Configuration Through Code Generation
**저자:** Claudio Provvedi, Lorenzo Seidenari, Benedetta Picano, Romano Fantacci
**출처 (학회/저널):** IEEE Transactions on Cognitive Communications and Networking, Vol. 12, 2026 (DOI: 10.1109/TCCN.2026.3683230)
**연도:** 2026
**링크:** https://doi.org/10.1109/TCCN.2026.3683230

**요약:**
IBN(Intent-Based Networking)에서 사용자의 선언적 의도를 Python 코드로 직접 변환하는 LLM 기반 프레임워크 **Intent-LLM**을 제안. ViperGPT에서 영감을 받아 네트워크 API를 정의하고, LLM이 해당 API를 호출하는 Python 코드를 생성하여 라우팅/자원 할당/토폴로지 수정 등의 네트워크 설정을 자동화.

**핵심 내용:**
- **접근 방식**: ViperGPT 패러다임 적용 — LLM이 Python 코드를 생성하고, 미리 정의된 네트워크 API 함수를 호출
- **네트워크 시뮬레이터**: SimPy 기반 Python 시뮬레이터 자체 개발
- **API 설계**: Docstring 기반 간결한 문서화 + Query-Code 페어링(in-context few-shot examples)
- **유연성/모듈성**: 새 기능 추가 시 API 모듈만 추가하면 LLM이 자동으로 활용
- **인텐트 분류**: User Low-specificity(UL), User High-specificity(UH), Operator Low-specificity(OL), Operator High-specificity(OH)
- **평가 지표**:
  - Syntactical Correctness: API 클래스/메서드명 정확도
  - Human Comparison: 석사 과정 학생 프로그래머 기준 대비 의도 이해 정확도
- **결과**: GPT 기반 모델이 Llama 3.3 대비 일관되게 높은 구문 정확도. 네트워크 규모 확장 시에도 성능 저하 없음

**내 연구와의 관련성:**
- **Intent→Code 방식 비교**: 우리 연구는 Intent→FlowRule JSON 생성이지만, 이 논문의 Intent→Python Code 방식과 비교/대조 가능 → Related Work에서 두 접근법 차이 설명
- **API 기반 LLM 구조**: 우리의 ONOS REST API 연동 설계에 참고 (LLM이 API 스펙 기반으로 호출 코드 생성)
- **평가 방법**: Human Comparison 지표는 우리 논문 평가에 활용 가능 (사람이 작성한 FlowRule vs. LLM 생성 비교)
- **한계 극복 포인트**: 이 논문은 검증/XAI 없음 → 우리 연구의 Static Validator + Digital Twin + XAI가 차별점

---

## Paper 4

**제목:** LLM-Based AI Agent for Virtual Network Function Deployment
**저자:** Sukhyun Nam, Nguyen Van Tu, James Won-Ki Hong
**출처 (학회/저널):** Journal of Network and Systems Management (2026) 34:111 (DOI: 10.1007/s10922-026-10078-x)
**연도:** 2026
**링크:** https://doi.org/10.1007/s10922-026-10078-x

**요약:**
자연어 입력 기반 VNF(Virtual Network Function) 배포 자동화를 위한 LLM AI 에이전트를 제안. Few-shot learning + RAG + Multi-Agent Debate(MAD)를 결합하고, Kubernetes 기반 **Network Digital Twin(NDT)**에서 사전 검증 후 실제 네트워크에 배포. NDT 오류 로그를 LLM에 피드백하여 반복 개선(self-healing).

**핵심 내용:**
- **핵심 구성요소**:
  1. **Few-shot Learning**: MOP(Management/Operation Procedure) 문서 + 예시 코드로 컨텍스트 주입
  2. **RAG**: 도메인 특화 네트워킹 지식 베이스 — 오류 해결 시 관련 문서 검색. Input/Output 필터링으로 무관한 문서 차단
  3. **Multi-Agent Debate (MAD)**: 여러 LLM이 서로의 응답을 검토하며 합의 도출
  4. **Network Digital Twin (NDT)**: Kubernetes 환경에서 워크플로우 사전 검증 → 오류 발생 시 로그 추출 → LLM 재입력 → 반복 개선
- **Self-Healing**: NDT에서 검증 실패 시 에러 로그를 LLM에 주입하여 자동 수정 (Agentic 루프)
- **데이터셋**: 자체 구축 MOP 데이터셋으로 다양한 NF 배포 시나리오 평가
- **결과**: Prompt-only 상태에서 VNF 배포 불가능했던 LLM도 AI Agent를 통해 성공률 크게 향상
- **POSTECH 그룹**: 홍원기 교수 연구실 (Survey 논문과 동일 저자 포함)

**내 연구와의 관련성:**
- **Digital Twin 활용 패턴**: NDT에서 사전 검증 후 실제 배포 — 우리의 Mininet 기반 Digital Twin 검증 아이디어와 동일한 패턴. 직접 비교 및 차별화 가능
- **RAG + 필터링**: Input/Output 필터링 기법은 우리 RAG 모듈에서 무관한 문서 차단 설계에 참고
- **MAD (Multi-Agent Debate)**: 우리 파이프라인의 신뢰성 향상 방법으로 도입 검토 가능
- **Self-Healing 루프**: NDT 오류 → LLM 재입력 루프는 우리의 정책 검증 실패 시 재생성 메커니즘 설계와 동일한 구조
- **Related Work**: 같은 IBN 맥락에서 VNF 배포에 집중한 선행 연구 — 우리는 FlowRule 정책 생성 + XAI에 집중하므로 상호 보완적

---

## Paper 5

**제목:** A Comprehensive Survey on LLM-Based Network Management and Operations
**저자:** Jibum Hong, Nguyen Van Tu, James Won-Ki Hong
**출처 (학회/저널):** International Journal of Network Management, 2025 (DOI: 10.1002/nem.70029)
**연도:** 2025
**링크:** https://doi.org/10.1002/nem.70029

**요약:**
LLM 기반 네트워크 관리 전반을 다루는 54페이지 종합 서베이. 네트워크 설정, 장애 관리, 보안, 오케스트레이션 등 주요 영역에서 LLM 활용 사례를 체계적으로 분류하고, 주요 한계(환각, 실시간 처리, 도메인 적응)와 미래 연구 방향을 제시. POSTECH 홍원기 교수 연구팀.

**핵심 내용:**
- **주요 커버리지**:
  - Configuration Management: IBN + LLM으로 자연어 → 네트워크 정책 변환
  - Fault Management: 로그 분석 → 이상 탐지 → 예측 → 자동 복구
  - Network Security: 위협 탐지, IDS 로그 분석
  - Orchestration: NFV/SDN 오케스트레이션 자동화
- **LLM 강점**: 비정형 텍스트(로그, 문서, 설정 파일) 이해, 자연어 인터페이스, 복잡 태스크 추론
- **핵심 한계**:
  - **환각(Hallucination)**: 프로토콜 위반 설정 생성 — RAG, CoT로 완화 시도 중
  - **실시간 처리**: LLM 추론 지연이 ms급 네트워크 제어와 충돌
  - **도메인 적응**: 일반 텍스트 사전학습 → 네트워크 특화 데이터 부족
  - **Legacy 시스템 통합**: 기존 SNMP/NETCONF 등과의 연동 복잡성
- **Digital Twin 언급**: 생성된 명령의 유해성 검증을 위한 Digital Twin 시뮬레이션 필요성 명시 ("pipelines which replay every generated change in a digital twin may eliminate most of the hazardous commands")
- **미래 방향**: XAI, 멀티모달 LLM, 경량화(LoRA, distillation), Formal Verification 결합

**내 연구와의 관련성:**
- **Related Work 핵심 서베이**: 이 논문을 Related Work 도입부에서 인용하며 "기존 서베이가 지적한 한계(환각, 검증 부재)를 우리 연구가 Static Validator + Digital Twin + XAI로 해결"이라고 positioning 가능
- **연구 정당성 확보**: Survey가 명시적으로 Digital Twin + XAI를 미래 연구 방향으로 제시 → 우리 연구의 필요성 직접 뒷받침
- **한계 목록 활용**: Introduction에서 문제 정의 시 이 Survey의 한계 분류를 인용하여 동기 부여

---
