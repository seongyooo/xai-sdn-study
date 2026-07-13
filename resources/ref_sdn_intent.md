# SDN / Intent-based Networking 관련 논문

---

## Paper 1

**제목:** Intent-Driven 6G Service Orchestration: Grounded Translation, Validation, and Decomposition
**저자:** Diogo Martins, Vítor Cunha, Pedro Alvarez, Artur Ramos, João Rodrigues, Pedro Rito, Daniel Corujo, Susana Sargento (+ Ericsson Research 협력)
**출처 (학회/저널):** ICML 2026 (Machine Learning for Networking Workshop)
**연도:** 2026
**링크:** https://arxiv.org/abs/2606.28348

**요약:**
6G 환경에서 자연어 인텐트를 서비스 오케스트레이션 정책으로 변환하는 3단계 Agentic 파이프라인을 제안. TMF Intent 온톨로지 기반 **카탈로그 그라운딩 + SHACL 검증 + CSP/가중 집합 커버 분해**로 구성되며, LangGraph로 구현. 환각을 26pp 감소시키고 실현 불가능 인텐트 100% 정확 거부.

**핵심 내용:**
- **3단계 파이프라인**:
  1. **Catalog Grounding**: 자연어 인텐트를 TMF 서비스 카탈로그(YAML)와 매칭 — 존재하지 않는 서비스를 LLM이 "생성"하는 환각 방지. Context grounding이 환각 26pp 감소 달성
  2. **SHACL Validation**: W3C SHACL 규칙으로 생성된 인텐트 표현의 TMF 온톨로지 적합성 검증. 실현 불가능 인텐트 100% 정확 거부
  3. **RFSS Decomposition**: Constraint Satisfaction Problem + Weighted Set Cover 알고리즘으로 고수준 인텐트를 하위 도메인 정책으로 분해
- **LangGraph 구현**: 상태 기반(stateful) 멀티 에이전트 워크플로우
- **평가**: 97% 전체 성공률, Llama 3.1 70B 사용

**내 연구와의 관련성:**
- **SHACL 검증**: 우리의 Static Validator에서 SHACL 기반 정책 검증 도입 가능 — 형식적 검증 계층 추가
- **Grounding 전략**: 카탈로그/온톨로지 기반 그라운딩 → 우리의 RAG가 FlowRule 스펙/ONOS API 문서를 grounding 소스로 사용하는 설계와 동일한 패턴
- **LangGraph**: 우리의 파이프라인 구현 기술 스택으로 직접 활용 가능
- **환각 감소 실험**: Context grounding 26pp 환각 감소 수치는 우리 논문에서 RAG 도입 근거로 인용 가능

---

## Paper 2

**제목:** Intent-LLM: A Framework for Automated Network Configuration Through Code Generation
**저자:** Claudio Provvedi, Lorenzo Seidenari, Benedetta Picano, Romano Fantacci
**출처 (학회/저널):** IEEE Transactions on Cognitive Communications and Networking, Vol. 12, 2026 (DOI: 10.1109/TCCN.2026.3683230)
**연도:** 2026
**링크:** https://doi.org/10.1109/TCCN.2026.3683230

**요약:**
IBN에서 선언적 인텐트를 Python 코드로 변환하는 LLM 기반 프레임워크. ViperGPT 패러다임을 네트워킹에 적용 — 미리 정의된 네트워크 API를 LLM이 호출하는 Python 코드를 생성하여 라우팅, 자원 할당, 토폴로지 수정 자동화.

**핵심 내용:**
- **ViperGPT 기반 설계**: 비전-언어 모델의 서브루틴 분해 패러다임을 네트워킹에 적용
- **네트워크 API**: SimPy 기반 시뮬레이터 + Docstring 문서화 + Query-Code 페어링 in-context 학습
- **인텐트 분류**: UL/UH/OL/OH (사용자/운영자 × 저명세/고명세)
- **평가**: Syntactical Correctness + Human Comparison (석사 학생 기준)
- **결과**: GPT 기반 > Llama 3.3. 네트워크 규모 확장 시에도 성능 유지

**내 연구와의 관련성:**
- **Intent→Code vs. Intent→FlowRule**: 이 논문은 Python 코드 생성, 우리는 ONOS FlowRule JSON 생성 — Related Work에서 두 접근 방식의 차이를 차별점으로 명확히 서술
- **검증/XAI 부재가 우리의 차별점**: 이 논문은 생성 코드의 네트워크 안전성 검증과 설명 가능성을 다루지 않음 → 우리 연구의 Static Validator + DT + XAI가 핵심 기여
- **API 기반 접근**: LLM이 API 스펙을 보고 코드를 생성하는 방식 → 우리 ONOS API 연동 설계에 참고

---

## Paper 3

**제목:** LLM-Driven Approach for Safe and Secure Network Management by Design in IoT-Based Systems
**저자:** Slavko Petrovic, Dragan Bojic, Marko Batic, Nikola Teslic
**출처 (학회/저널):** Symmetry 2026, 18(3), 337 (DOI: 10.3390/sym18030337)
**연도:** 2026
**링크:** https://doi.org/10.3390/sym18030337

**요약:**
IoT 시스템을 위한 설계 시점(design-time) LLM 기반 네트워크 관리 워크플로우. MDE(Model-Driven Engineering) + OCL 규칙 + RAG + LLM + YANG/NETCONF 조합으로 기능 안전성(functional safety)과 보안 토폴로지(secure topology) 두 케이스 스터디에서 검증. 수동 대비 6-15배 속도 향상.

**핵심 내용:**
- **설계 시점 접근**: 런타임 정책 적용이 아닌 설계 단계에서 안전/보안 규칙 적용
- **MDE + OCL**: UML 활동 다이어그램으로 프로세스 모델링 → OCL 규칙으로 제약 조건 형식화
- **RAG 활용**: 표준 문서(YANG 모델, NETCONF 사양)를 RAG 소스로 사용
- **두 케이스 스터디**: (1) 기능 안전성 - 활동 다이어그램 기반 before/after 규칙, (2) 보안 토폴로지 - OCL 제약 조건
- **결과**: GPT-5: 90-100%, LLaMA 3.3 70B: 75-85% 성공률

**내 연구와의 관련성:**
- **OCL/형식 검증**: 우리 Static Validator의 규칙 충돌 탐지에 OCL 스타일 제약 조건 적용 가능
- **YANG/NETCONF**: 우리의 FlowRule이 YANG 모델과 어떻게 연관되는지 설명하는 배경 논문으로 활용
- **설계 시점 vs. 런타임**: 이 논문은 설계 시점 검증에 집중, 우리는 런타임 정책 생성+검증 — Related Work에서 두 접근의 상호 보완성 설명
- **XAI 언급**: 약어 목록에 XAI 포함 — 설명 가능성 방향으로 확장 가능성 시사

---

## Paper 4

**제목:** Bridging Language Models and Formal Methods for Intent-Driven Optical Network Design
**저자:** Anis Bekri, Amar Abane, Abdella Battou, Saddek Bensalem (NIST + Univ. Grenoble Alpes)
**출처 (학회/저널):** AICCSA 2025
**연도:** 2025
**링크:** https://arxiv.org/abs/2509.22834

**요약:**
자연어 인텐트를 배포 가능한 광학 네트워크 설계로 변환하는 하이브리드 파이프라인. LLM의 의미 이해 능력과 형식 검증의 수학적 엄밀성을 결합. **CFG(문맥 자유 문법) 구조 검증 + Optical RAG + PDDL 형식 계획** 3단계 구성. GPT-4 단독 사용 시 실행 가능한 계획이 12%에 불과하다는 한계를 극복.

**핵심 내용:**
- **3단계 파이프라인**:
  1. **Intent Parser & Validation (CFG)**:
     - LLM이 자연어를 문법 준수 형식으로 변환
     - CFG로 구조 검증 → 환각 탐지 (모호한 예산값 "fair" → 수치 요구 → 거부)
     - 오류 분류: LLM-fixable (자동 재프롬프트) vs. user-required (사람 개입 필요)
     - 출력: 구조화된 Intent JSON + 형식화된 제약 조건
  2. **Formal Planning & Design (PDDL)**:
     - PDDL(Planning Domain Definition Language)로 네트워크 배포 계획 검증
     - 파장 연속성, 지연 예산, 이중화, 장비 배치 제약 조건 충족 보장
  3. **Optical RAG**:
     - ITU-T, IEEE 광학 표준 + 벤더 장비 사양 벡터 DB
     - TelcoRAG 방식을 3GPP → 광학 네트워크 도메인으로 적용

- **핵심 인사이트**: CFG가 LLM 환각을 구조적 위반으로 탐지 — 명확한 정보가 없을 때 LLM이 할루시네이션하면 CFG가 형식 위반으로 잡아냄
- **한계**: GPT-4 단독 12% 실행 가능 → 파이프라인 도입 필요성 수치로 제시

**내 연구와의 관련성:**
- **CFG = 우리의 Static Validator**: 문법/형식 규칙으로 LLM 출력의 구조적 오류를 잡는 방식 — 우리의 FlowRule JSON 스키마 검증에 동일 패턴 적용 가능
- **PDDL 형식 계획**: 우리의 Digital Twin 검증 전 단계로 PDDL 스타일 형식 계획 검증 추가 검토 가능
- **Optical RAG**: 도메인 표준을 RAG 소스로 사용하는 방식을 우리의 ONOS API 문서 + OpenFlow 스펙 RAG에 동일 적용
- **환각을 형식 위반으로 탐지**: 이 아이디어를 우리 FlowRule 검증에 적용 — LLM이 존재하지 않는 액션 타입을 생성하면 JSON 스키마 검증이 즉시 탐지
- **GPT-4 12% 수치**: 우리 Introduction에서 "LLM 단독 사용의 한계" 논증에 인용 가능

---

## Paper 5

**제목:** NetIntent: Leveraging Large Language Models for End-to-End Intent-Based SDN Automation
**저자:** Md. Kamrul Hossain, Walid Aljoby (King Fahd University of Petroleum and Minerals)
**출처 (학회/저널):** IEEE Open Journal of Communications Society, Vol. 6, 2025 (DOI: 10.1109/OJCOMS.2025.3642642)
**연도:** 2025
**링크:** https://doi.org/10.1109/OJCOMS.2025.3642642

**요약:**
자연어 인텐트 → FlowRule JSON → 충돌 탐지 → ONOS 배포 → Intent Assurance까지 전체 IBN 라이프사이클을 LLM으로 자동화하는 **NetIntent** 프레임워크. 동시에 **IBNBench** 벤치마크 (Intent2Flow-ONOS, FlowConflict-ONOS 포함 총 8개 데이터셋) 공개. 33개 오픈소스 LLM 성능 비교. LEAD-Drift와 동일 저자팀(KFUPM).

**핵심 내용:**
- **3단계 IBN 라이프사이클**:
  1. **Intent Translation**: 자연어 → LLM (few-shot) → FlowRule JSON → JSON 검증기 → 실패 시 오류 피드백 + 재생성
  2. **Intent Activation**: LLM 기반 충돌 탐지 → 충돌 해결 → ONOS 배포
  3. **Intent Assurance**: 비-LLM 에이전트로 Intent Drift + 실제 네트워크 상태 모니터링 → LLM에 피드백 → 수정 행동 생성

- **IBNBench 데이터셋** (공개):
  - `Intent2Flow-ODL/ONOS/Ryu/Floodlight`: 자연어 인텐트 → FlowRule JSON 페어
  - `FlowConflict-ODL/ONOS/Ryu/Floodlight`: FlowRule 충돌 여부 레이블
  - **Intent2Flow-ONOS, FlowConflict-ONOS** → 우리 실험에 직접 사용 가능

- **33개 LLM 벤치마크**:
  - QwQ-fusion(32b), Command-r(35b): 99-100% 정확도
  - 중형 모델(Codellama:7b, Mistral:7b): context 예시 추가 시 최대 +20-30%
  - In-context 예시 수가 성능에 결정적 영향

- **지원 컨트롤러**: ODL, ONOS, Ryu, Floodlight

- **없는 것**: RAG ✗, Digital Twin ✗, XAI ✗

**내 연구와의 관련성:**
- ⚠️ **가장 가까운 선행 연구**: Intent2Flow-ONOS + FlowConflict-ONOS를 이미 구현 — 우리와 태스크가 거의 동일. Related Work에서 가장 비중 있게 다뤄야 할 논문
- **차별화 포인트 명확화**:
  - NetIntent: Few-shot in-context 학습 / 우리: RAG (문서 검색 기반) — 도메인 지식 주입 방식이 다름
  - NetIntent: DT 없음 / 우리: Mininet DT로 배포 전 안전 검증
  - NetIntent: XAI 없음 / 우리: SHAP + LLM 자연어 설명 — **핵심 차별점**
- **IBNBench 활용**: Intent2Flow-ONOS 데이터셋을 우리 실험 평가에 직접 사용 → 데이터셋 자체 구축 부담 감소, 선행 연구와 직접 수치 비교 가능
- **논문 포지셔닝**: "NetIntent가 자동화 파이프라인을 달성했지만 '왜 이 정책이 안전한가?'를 설명하지 못한다 → 본 연구가 XAI와 DT로 신뢰성을 추가"

---
