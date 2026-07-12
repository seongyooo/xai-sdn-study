# RAG (Retrieval-Augmented Generation) 관련 논문

---

## Paper 1

**제목:** LLM-Based AI Agent for Virtual Network Function Deployment
**저자:** Sukhyun Nam, Nguyen Van Tu, James Won-Ki Hong (POSTECH)
**출처 (학회/저널):** Journal of Network and Systems Management (2026) 34:111 (DOI: 10.1007/s10922-026-10078-x)
**연도:** 2026
**링크:** https://doi.org/10.1007/s10922-026-10078-x

**요약:**
VNF 배포 자동화에서 **RAG + Input/Output 필터링**을 활용한 Self-Healing LLM 에이전트. NDT(Network Digital Twin) 검증 실패 시 오류 로그를 쿼리로 사용하여 관련 문서를 검색하고 LLM에 주입. 무관한 문서 차단을 위한 필터링이 성능 핵심 요소.

**핵심 내용:**
- **RAG 파이프라인**:
  - 소스: 도메인 특화 네트워크 운영 문서(MOP), 설정 매뉴얼
  - 쿼리: NDT 실행 오류 메시지 → 관련 해결책 문서 검색
  - **Input 필터링**: 오류 메시지에서 핵심 키워드 추출 → 정밀 검색
  - **Output 필터링**: 검색된 문서 중 현재 오류와 무관한 것 제거
- **MAD (Multi-Agent Debate)**: 여러 LLM이 동일 오류에 대한 해결 방안을 제시하고 교차 검토
- **효과**: 무관한 문서가 RAG에 포함될 때 오히려 성능 저하 → 필터링의 중요성 입증
- **실험**: 초기 실패 LLM도 RAG+MAD로 VNF 배포 성공

**내 연구와의 관련성:**
- **RAG 필터링 설계**: Input/Output 필터링을 우리의 FlowRule RAG에 도입 — "관련 FlowRule 규칙/정책 예시만 선택적으로 검색"
- **오류 기반 RAG 쿼리**: 검증 실패 오류 메시지 → RAG 쿼리로 활용 → 올바른 정책 예시 검색 → LLM 재생성 — 우리 파이프라인의 자가 수정 루프에 적용
- **MAD 도입 가능성**: 여러 LLM의 교차 검토는 우리의 FlowRule 생성 신뢰성 향상 방법으로 검토 가능

---

## Paper 2

**제목:** AI-Driven Framework for Adaptive Water Network Management Using Digital Twin, LLM, and RAG
**저자:** Musbah Fasha, Baha Rababah, Diya'a Al-Akayleh (Univ. of Petra, Jordan)
**출처 (학회/저널):** arXiv:2606.15709v1 [cs.AI]
**연도:** 2026
**링크:** https://arxiv.org/abs/2606.15709

**요약:**
EPANET Digital Twin + Llama 3.1:8b(Ollama 오프라인) + **FAISS 기반 RAG**로 수도 네트워크를 자연어로 관리. RAG가 수도 공학 도메인 지식을 LLM에 주입하여 도메인 특화 응답과 정확한 제어 명령 생성.

**핵심 내용:**
- **FAISS 벡터 DB**: 수도 공학 문서를 임베딩하여 저장 → 유사도 기반 검색
- **오프라인 RAG**: 모든 구성요소 로컬 실행 (데이터 프라이버시 보장)
- **Function Calling + RAG 결합**: RAG로 관련 지식 주입 → LLM이 정확한 API 함수 호출 결정
- **응답 시간**: 2분 이내 (1,164 접합부 네트워크)

**내 연구와의 관련성:**
- **FAISS 구현 참고**: 우리의 FlowRule 규칙 문서, ONOS API 스펙, 과거 정책 예시를 FAISS로 인덱싱하는 구현에 참고
- **RAG 소스 설계**: 수도 공학 문서처럼 우리는 (1) OpenFlow/ONOS 공식 문서, (2) FlowRule 스펙, (3) 과거 유사 인텐트-FlowRule 페어를 RAG 소스로 사용

---

## Paper 3

**제목:** Intent-Driven 6G Service Orchestration: Grounded Translation, Validation, and Decomposition
**저자:** Diogo Martins et al. (Ericsson Research 협력)
**출처 (학회/저널):** ICML 2026
**연도:** 2026
**링크:** https://arxiv.org/abs/2606.28348

**요약:**
6G 서비스 오케스트레이션에서 **카탈로그 그라운딩(Catalog Grounding)**을 통해 LLM 환각을 방지. TMF 서비스 카탈로그(YAML)를 컨텍스트로 주입 → 존재하지 않는 서비스 생성 방지 → 환각 26pp 감소. RAG와 유사한 grounding 메커니즘.

**핵심 내용:**
- **카탈로그 기반 Grounding**: RAG의 특수한 형태 — 전체 텍스트 검색이 아닌 구조화된 카탈로그(YAML) 매칭
- **환각 방지 효과**: Context grounding으로 26pp 환각 감소 (수치 측정)
- **SHACL 검증과 연계**: Grounding으로 생성된 인텐트 표현을 SHACL로 형식 검증
- **실현 불가능 인텐트 거부**: 카탈로그에 없는 서비스 요청 시 정확하게 거부 (100% 정확도)

**내 연구와의 관련성:**
- **환각 방지 RAG 설계**: 우리의 RAG에서도 단순 유사도 검색 외에 ONOS API 카탈로그/FlowRule 스펙 구조화 매칭 추가 → 존재하지 않는 액션 유형 생성 방지
- **26pp 환각 감소 수치**: 우리 논문에서 "RAG 도입 효과"를 주장할 때 이 논문 인용 가능
- **LangGraph 구현**: 우리의 파이프라인 구현 참고

---
