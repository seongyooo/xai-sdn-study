# Digital Twin 관련 논문

---

## Paper 1

**제목:** LLM-Based AI Agent for Virtual Network Function Deployment
**저자:** Sukhyun Nam, Nguyen Van Tu, James Won-Ki Hong (POSTECH)
**출처 (학회/저널):** Journal of Network and Systems Management (2026) 34:111 (DOI: 10.1007/s10922-026-10078-x)
**연도:** 2026
**링크:** https://doi.org/10.1007/s10922-026-10078-x

**요약:**
VNF 배포 자동화 LLM 에이전트에서 **Kubernetes 기반 Network Digital Twin(NDT)**을 활용한 사전 검증 메커니즘을 제시. LLM이 생성한 배포 워크플로우를 NDT에서 먼저 실행 → 오류 발생 시 로그를 LLM에 피드백 → 반복 수정(self-healing) → 성공 시 실제 네트워크 배포.

**핵심 내용:**
- **NDT 역할**: 실제 네트워크 적용 전 안전 검증 환경. Kubernetes 기반
- **Self-Healing 루프**: NDT 실행 실패 → 오류 로그 추출 → LLM 재입력 → 워크플로우 재생성 → NDT 재검증 반복
- **RAG 연동**: 오류 해결 시 도메인 지식 검색 — Input/Output 필터링으로 무관 문서 차단
- **MAD (Multi-Agent Debate)**: 여러 LLM의 교차 검토로 신뢰성 향상
- **결과**: Prompt-only로 불가능했던 VNF 배포를 NDT 피드백 루프로 해결
- **핵심 기여**: IBN의 Translation(의도→워크플로우) + Activation(검증→배포) 단계 자동화

**내 연구와의 관련성:**
- **Digital Twin 설계 선행 연구**: Kubernetes NDT → 우리는 Mininet 기반 SDN DT로 동일한 개념 적용. 비교 포인트: 환경(Kubernetes vs. Mininet), 태스크(VNF 배포 vs. FlowRule 정책), 검증 방법
- **Self-Healing 루프 = 우리의 핵심 메커니즘**: 검증 실패 → 오류 피드백 → LLM 재생성 구조가 우리 파이프라인의 핵심 — 이 논문으로 접근법 타당성 검증
- **차별화 포인트**: 이 논문은 XAI 설명 없음 + FlowRule/정책 수준이 아닌 배포 레벨 → 우리 연구가 XAI와 정책 충돌 검증을 추가하는 기여 명확화
- **RAG 필터링**: Input/Output 필터링 설계는 우리 RAG 모듈 구현에 직접 적용 가능

---

## Paper 2

**제목:** AI-Driven Framework for Adaptive Water Network Management Using Digital Twin, LLM, and RAG
**저자:** Musbah Fasha, Baha Rababah, Diya'a Al-Akayleh (Univ. of Petra, Jordan)
**출처 (학회/저널):** arXiv:2606.15709v1 [cs.AI]
**연도:** 2026
**링크:** https://arxiv.org/abs/2606.15709

**요약:**
수도 네트워크 관리에 Digital Twin + LLM + RAG를 결합한 프레임워크. **EPANET** 시뮬레이터를 Digital Twin으로 활용하고, **Llama 3.1:8b**(Ollama 로컬 오프라인 실행) + **FAISS** 기반 RAG로 자연어 질의에 응답 및 네트워크 제어 명령 생성. 2분 이내 응답.

**핵심 내용:**
- **Digital Twin 역할**: EPANET 시뮬레이터로 수도 네트워크 디지털 복제본 구축
  - 실제 배포 전 시뮬레이션 테스트
  - 네트워크 상태 모니터링 + 이상 탐지
  - "what-if" 시나리오 분석
- **Function Calling**: LLM이 EPANET API 함수를 직접 호출하여 네트워크 파라미터 조정
- **RAG**: FAISS 벡터 DB에 수도 공학 문서 저장 → 질의 시 관련 컨텍스트 검색
- **오프라인 동작**: Ollama로 로컬 실행 — 네트워크 인프라 도메인의 보안/프라이버시 요구사항 충족
- **실험**: 1,164개 접합부 암만(요르단) 수도 네트워크 적용 POC
- **한계**: 소규모 POC, 실제 운영 환경 검증 부족

**내 연구와의 관련성:**
- **DT + LLM + RAG 조합 선행 연구**: 네트워크 도메인이 다르지만(수도 vs. SDN) 동일한 아키텍처 패턴 — Related Work에서 "다양한 도메인에서 DT+LLM+RAG가 검증됨"으로 인용
- **Function Calling 방식**: LLM이 시뮬레이터 API를 직접 호출하는 방식 → 우리의 ONOS REST API 호출 설계와 동일
- **오프라인 LLM**: 보안 네트워크 환경에서 로컬 LLM 사용 — 우리 연구에서 배포 옵션으로 언급 가능
- **RAG 설계 참고**: FAISS 기반 RAG → 우리의 FlowRule 문서/표준 RAG 구현에 참고

---

## Paper 3

**제목:** Digital Twin Assisted Proactive Management in Zero Touch Networks
**저자:** Tamizhelakkiya K, Dibakar Das, Komal Sharma, Jyotsna Bapat, Debabrata Das (IIIT Bangalore + Toshiba)
**출처 (학회/저널):** IEEE FNWF 2025 (preprint arXiv:2508.17941)
**연도:** 2025
**링크:** https://arxiv.org/abs/2508.17941

**요약:**
Zero Touch Network(ZTN)에서 Digital Twin을 활용한 선제적 대역폭 관리 프레임워크. Few-Shot Learning 기반 메모리 증강 BiLSTM으로 네트워크 상태 예측 → Q-learning으로 최적 행동(트래픽 쉐이핑 등) 결정. LLM 없음, 전통 ML 기반.

**핵심 내용:**
- **3계층 아키텍처**: 사용자 → DT 기반 ZTN 폐쇄 루프 제어 → 물리 네트워크
- **Digital Twin 역할**:
  - 실시간 네트워크 상태 모니터링
  - What-if 시나리오 시뮬레이션 (배포 전 가상 검증)
  - 예측 분석 (대역폭 변화 예측)
- **FSL BiLSTM**: 학습된 상태 + 새 상태를 메모리 증강으로 통합 → 대역폭 예측
- **Q-learning**: 예측 상태 기반 최적 행동(트래픽 쉐이핑) 결정 → QoS 보장
- **3가지 시나리오 평가**: 정상 ZTN 운영 / DT what-if / DT가 모르는 새 네트워크 상태
- **결과**: DT 지원 ZTN이 DT 없는 기준 대비 우수한 QoS 성능

**내 연구와의 관련성:**
- **DT What-if 시나리오 = 우리의 핵심**: 실제 배포 전 DT에서 FlowRule 효과를 시뮬레이션하는 아이디어와 동일. "DT가 배포 전 검증 환경으로 기능한다"는 개념 인용 가능
- **ZTN 자동화 맥락**: Zero Touch = 사람 개입 최소화 → 우리의 LLM 기반 자동 정책 생성과 동일한 방향성
- **차별화**: 이 논문은 LLM 없음 + SDN FlowRule 아님 + XAI 없음 → 우리가 LLM+RAG+XAI를 추가한 SDN 특화 버전
- **Related Work 배경**: ZTN + DT 자동화의 선행 연구로 인용하며 "LLM을 추가하면 자연어 인터페이스가 가능해진다"는 논증에 활용

---
