# XAI + LLM/RAG 기반 Intent-Driven SDN 자동화 — 공부 로드맵

> 목표: Digital Twin 검증 + XAI 설명이 결합된 LLM/RAG 기반 안전한 SDN 자동화 시스템 이해 및 구현

---

## 전체 구조 한눈에 보기

```
[사용자 자연어 인텐트]
        ↓
   LLM / RAG
        ↓
  SDN 정책 후보 생성
        ↓
  Static Validator      ← 룰 충돌 정적 검사
        ↓
  Digital Twin          ← 시뮬레이션 사전 검증
        ↓
  XAI Layer             ← 판단 근거 설명
        ↓
  ONOS 컨트롤러 적용
```

---

## Phase 1. SDN 기초

### 핵심 개념
- **Control Plane vs Data Plane 분리**: SDN의 핵심. 제어 기능을 소프트웨어로 분리.
- **OpenFlow**: Control Plane ↔ Data Plane 간 표준 통신 인터페이스 (Southbound API)
- **FlowTable**: 스위치 내부의 패킷 전달 규칙 테이블 (Match + Action)
- **SDN Controller**: 전체 네트워크의 글로벌 뷰를 가진 중앙 제어 소프트웨어

### SDN 3계층 아키텍처
| 계층 | 역할 | 예시 |
|------|------|------|
| Application Layer | 네트워크 제어 앱 | Routing, Load Balancing, ACL |
| Control Plane | 중앙 네트워크 OS | ONOS, OpenDaylight, Ryu |
| Data Plane | 패킷 전달 장치 | OpenFlow Switch, OVS |

### 인터페이스
- **Southbound API**: 컨트롤러 ↔ 스위치 (ex. OpenFlow, NETCONF)
- **Northbound API**: 컨트롤러 ↔ 애플리케이션 (REST API)

### 참고 자료
- `resources/sdn_openflow_intro.md` — SDN/OpenFlow 개념 블로그 스크랩
- `resources/sdnhistory.pdf` → `papers/` 이동됨
- `papers/JAKO201302757805044.pdf` — OpenFlow 관련 한국 논문

---

## Phase 2. ONOS + Mininet 실습 환경

### ONOS (Open Network Operating System)
- ONF 주도로 개발된 오픈소스 SDN 컨트롤러
- 분산 아키텍처, 통신사급 네트워크 대상
- Web UI: `http://localhost:8181/onos/ui` (onos/rocks)

### Mininet
- 가상 네트워크 토폴로지 시뮬레이터
- 실제 OpenFlow 스위치(OVS)와 호스트를 소프트웨어로 에뮬레이션
- 명령어: `sudo mn --topo single,3 --controller remote,ip=127.0.0.1,port=6653 --switch ovsk,protocols=OpenFlow13`

### 실습 체크리스트
- [ ] ONOS Docker 실행 및 Web UI 접속
- [ ] OpenFlow Provider / Reactive Forwarding 앱 활성화
- [ ] Mininet single,3 토폴로지 연결
- [ ] pingall 0% loss 확인
- [ ] ONOS REST API로 FlowRule 직접 조작
- [ ] 토폴로지 변경 시 흐름 변화 관찰

### 참고
- `archive/explainable_sdn_repo_archive.md` — 실습 환경 구축 상세 가이드 포함

---

## Phase 3. LLM / RAG 기초

### LLM (Large Language Model)
- 자연어 인텐트를 SDN 정책으로 변환하는 핵심 엔진
- 문제: 환각(Hallucination), 도메인 지식 부족, 잘못된 설정 생성

### RAG (Retrieval-Augmented Generation)
- LLM의 도메인 적응 문제를 해결하는 방법
- 관련 문서/정책을 벡터 DB에서 검색 → LLM 프롬프트에 컨텍스트로 주입
- 구성: `문서 임베딩 → 벡터 DB 저장 → 쿼리 시 유사 문서 검색 → LLM 입력`

### 공부할 것
- [ ] LLM 프롬프트 엔지니어링 기초
- [ ] RAG 파이프라인 구조 (LangChain / LlamaIndex)
- [ ] 임베딩 모델 개념 (Sentence Transformer 등)
- [ ] 벡터 DB 개념 (FAISS, Chroma, Weaviate)

---

## Phase 4. XAI (Explainable AI)

### 왜 필요한가
- LLM이 생성한 SDN 정책이 "왜 안전한지" 사람이 납득할 수 있어야 함
- 네트워크 장애 발생 시 원인 추적 가능해야 함

### XAI 주요 기법
| 기법 | 설명 | 적용 포인트 |
|------|------|------------|
| LIME | 개별 예측을 로컬 선형 모델로 근사 설명 | 정책 생성 근거 |
| SHAP | 특성 기여도를 Shapley 값으로 계산 | 어떤 네트워크 상태가 정책에 영향? |
| Attention Visualization | LLM 어텐션 가중치 시각화 | 어떤 컨텍스트를 참조했는가? |
| Rule Extraction | 모델 판단을 if-then 룰로 변환 | 사람이 읽을 수 있는 정책 설명 |

### 공부할 것
- [ ] LIME / SHAP 개념 및 실습
- [ ] LLM 어텐션 시각화
- [ ] 네트워크 도메인에서의 XAI 적용 사례

---

## Phase 5. Digital Twin (디지털 트윈)

### 개념
- 실제 네트워크의 가상 복제본
- SDN 정책을 실제 적용 전에 시뮬레이션으로 사전 검증

### SDN에서의 역할
```
생성된 SDN 정책
      ↓
Digital Twin (Mininet 기반 가상 네트워크)
      ↓
트래픽 시뮬레이션 → 장애/충돌 감지
      ↓
안전하면 → 실제 ONOS 컨트롤러 적용
실패하면 → 정책 재생성 요청
```

### 공부할 것
- [ ] Mininet을 Digital Twin으로 활용하는 방법
- [ ] ONOS REST API로 정책 자동 적용 및 검증
- [ ] 네트워크 상태 모니터링 (트래픽, 지연, 손실률)

---

## Phase 6. Static Validator

### 역할
- Digital Twin 이전 단계의 빠른 사전 필터링
- LLM이 생성한 FlowRule에서 정적으로 충돌/오류 감지

### 검사 항목 (예시)
- 동일 우선순위 + 동일 매치 룰 중복
- 루프 유발 가능성
- 접근 제어 정책 위반 (ACL 충돌)
- 포트 범위 오류

### 공부할 것
- [ ] OpenFlow FlowRule 구조 (Match + Action + Priority)
- [ ] 룰 충돌 탐지 알고리즘
- [ ] Python으로 간단한 정적 분석기 구현

---

## Phase 7. 전체 통합 파이프라인 구현

### 목표 흐름
```
자연어 인텐트 입력
   → RAG로 관련 정책 검색 + LLM으로 FlowRule 생성
   → Static Validator로 정적 검사
   → Digital Twin(Mininet)에서 시뮬레이션
   → XAI Layer로 판단 근거 생성
   → 안전 확인 시 ONOS REST API로 실제 적용
```

### 구현 순서
- [ ] ONOS REST API 클라이언트 (Python)
- [ ] Mininet 자동 제어 스크립트
- [ ] LLM + RAG 파이프라인
- [ ] Static Validator 모듈
- [ ] Digital Twin 검증 모듈
- [ ] XAI 설명 모듈
- [ ] 전체 파이프라인 연결

---

## 참고 논문 / 자료 목록

| 파일 | 내용 |
|------|------|
| `papers/JAKO201302757805044.pdf` | OpenFlow 관련 한국 논문 |
| `papers/sdnhistory.pdf` | SDN 역사 (The Road to SDN) |
| `resources/sdn_openflow_intro.md` | SDN/OpenFlow 블로그 스크랩 |
| `archive/explainable_sdn_repo_archive.md` | 클론 레포 구조 및 실습 내용 |
