# 프로젝트 로드맵

> **목표**: 제7회 한국 인공지능 학술대회 (KICS) 논문 제출
> **마감**: 2026-08-24
> **남은 기간**: 6주 (2026-07-12 기준)

---

## 전체 타임라인

```
7/12  7/19  7/26  8/2   8/9   8/16  8/24
 │     │     │     │     │     │     │
 ├─1주─┼─2주─┼─3주─┼─4주─┼─5주─┼─6주─┤
 환경  RAG   Static  DT   XAI  논문  마감
 셋업  +LLM  Valid.  검증  설명  작성
```

---

## 구현할 시스템

```
[자연어 인텐트]
      ↓
[LLM + RAG]  ← FAISS + FlowRule 문서
      ↓
[Static Validator]  ← 스키마/충돌 검사
      ↓
[Digital Twin]  ← Mininet 사전 검증
      ↓
[XAI Layer]  ← SHAP + LLM 자연어 설명
      ↓
[ONOS REST API]  ← 실제 배포
```

---

## Week 1 — 환경 셋업 (7/12 ~ 7/18)

### 목표
실험 가능한 ONOS + Mininet 환경 구축

### 할 일
- [ ] Docker로 ONOS 실행 (`onosproject/onos:latest`)
- [ ] Web UI 접속 확인 (`localhost:8181/onos/ui`, onos/rocks)
- [ ] OpenFlow Provider / Reactive Forwarding 앱 활성화
- [ ] Mininet 설치 및 basic 토폴로지 연결
  ```bash
  sudo mn --topo single,3 --controller remote,ip=127.0.0.1,port=6653 --switch ovsk,protocols=OpenFlow13
  ```
- [ ] `pingall` 0% loss 확인
- [ ] Python으로 ONOS REST API FlowRule 추가/삭제 테스트
- [x] LLM API 키 세팅 (Gemini API)
- [x] LangChain, FAISS, pydantic 패키지 설치

### 완료 기준
Python 스크립트로 ONOS에 FlowRule을 추가하면 Mininet에서 트래픽 변화 확인 가능

---

## Week 2 — LLM + RAG 파이프라인 ✅ (7/13 완료, 예정보다 1주 앞당김)

### 목표
자연어 인텐트 → FlowRule JSON 생성

### 할 일
- [x] FlowRule JSON 스키마 정의 (ONOS REST API 형식 기준)
  ```json
  {
    "priority": 40000,
    "timeout": 0,
    "isPermanent": true,
    "deviceId": "of:0000000000000001",
    "treatment": { "instructions": [{"type": "OUTPUT", "port": "2"}] },
    "selector": { "criteria": [{"type": "ETH_TYPE", "ethType": "0x800"}, {"type": "IPV4_DST", "ip": "10.0.0.2/32"}] }
  }
  ```
- [x] RAG 지식베이스 구축
  - IBNBench Intent2Flow-ONOS 데이터셋 활용 (25쌍 train)
  - gemini-embedding-001로 벡터화
- [x] FAISS 벡터 DB 구축 (문서 임베딩 저장)
- [x] LangChain 파이프라인 구현
  - 인텐트 입력 → 유사 예시 검색 → 프롬프트 구성 → LLM 호출 → JSON 출력
- [x] 25개 테스트 케이스로 생성 품질 확인 (RAG 96.0%, Few-shot 대비 안정적)

### 인텐트 예시
```
"10.0.0.1에서 10.0.0.2로 가는 HTTP 트래픽을 포트 2로 전달해"
"10.0.0.3의 모든 트래픽을 차단해"
"서버(10.0.0.10)로 가는 트래픽을 포트 3과 4에 로드밸런싱해"
```

### 완료 기준
임의의 자연어 인텐트 입력 → 유효한 ONOS FlowRule JSON 출력

---

## Week 3 — Static Validator ✅ (7/13 완료, 예정보다 2주 앞당김)

### 목표
FlowRule의 정적 오류/충돌을 LLM 배포 전에 탐지

### 할 일
- [x] JSON 스키마 검증 (Pydantic)
  - 필수 필드, 타입 오류, 범위 초과, LLM 환각 탐지 → **10/10 = 100%**
- [x] 규칙 충돌 탐지
  - Rule-based (97.3%) + LLM-based (98.6%) 두 방식 모두 구현
  - FlowConflict-ONOS 74쌍으로 평가
- [x] 충돌 이유 자연어 설명 생성 (NetIntent 차별점)
  - Shadowing / Imbrication / Correlation / Redundancy / Generalization 5가지 유형 설명
- [x] 오류 메시지 → LLM 재생성 피드백 루프 설계 완료

### 완료 기준
의도적으로 잘못된 FlowRule 입력 시 오류 유형 탐지 + 자동 재생성 성공

---

## Week 4 — Digital Twin + XAI (8/2 ~ 8/8)

### 목표 1: Mininet Digital Twin 검증
- [ ] Mininet 토폴로지 자동 생성 스크립트 (Python API)
- [ ] Static Validator 통과한 FlowRule → Mininet에 자동 적용
- [ ] 트래픽 테스트 자동화 (pingall, iperf)
- [ ] 검증 실패 시 에러 로그 추출 → LLM 재생성 피드백

### 목표 2: XAI 설명 모듈
- [ ] SHAP 분석: 인텐트의 어떤 특성이 FlowRule 선택에 영향을 줬는지
  - 예: "포트 번호 80이 HTTP 분류에 기여"
- [ ] LLM으로 SHAP 결과 → 자연어 설명 변환
  ```
  "이 FlowRule은 목적지 IP(10.0.0.2)와 프로토콜(HTTP)을 기준으로 생성됐습니다.
   RAG 검색 결과 유사한 L3 포워딩 정책 3개를 참조했으며,
   Static Validator를 통해 기존 규칙과의 충돌이 없음을 확인했습니다."
  ```
- [ ] 설명 출력 형식 정의 (텍스트 + 주요 근거 목록)

### 완료 기준
인텐트 입력 → FlowRule 생성 → 검증 → XAI 설명까지 자동으로 실행되는 End-to-End 파이프라인

---

## Week 5 — 실험 평가 + 논문 작성 시작 (8/9 ~ 8/15)

### 실험 설계
- [ ] **테스트 케이스 구성** (20~30개 인텐트)
  - 카테고리별: L2 포워딩, L3 라우팅, ACL, QoS, 로드밸런싱
  - 난이도별: 단순/복합/모호한 표현

- [ ] **평가 지표**
  | 지표 | 측정 방법 |
  |------|-----------|
  | FlowRule 구문 정확도 | JSON 스키마 유효 비율 |
  | 의미 정확도 | 인간 평가 (0~5점) |
  | DT 검증 통과율 | Mininet pingall/iperf 성공 비율 |
  | XAI 설명 품질 | Usefulness / Correctness 인간 평가 |
  | 평균 처리 시간 | 인텐트 입력 → 배포까지 |
  | 재생성 횟수 | 검증 실패 시 LLM 재시도 횟수 |

- [ ] **비교 실험**
  - RAG 없는 LLM 단독 vs. RAG 포함
  - Static Validator 없음 vs. 있음
  - XAI 설명 품질 측정

- [ ] 실험 결과 정리 (표, 그래프)

### 논문 작성 시작
- [ ] Abstract 초안
- [ ] Introduction 초안 (문제 정의 + 기여점)
- [ ] System Design 섹션 (파이프라인 그림 포함)

---

## Week 6 — 논문 완성 + 제출 (8/16 ~ 8/24)

### 논문 구성
```
1. Abstract          (~150단어)
2. Introduction      문제 정의, 기존 연구 한계, 기여점
3. Related Work      분석한 논문 13개 활용
4. System Design     전체 파이프라인 + 각 모듈 설명
5. Evaluation        실험 결과 + 표 + 그래프
6. Conclusion        요약 + 향후 연구
```

### 할 일
- [ ] Related Work 작성 (ref_*.md 파일 활용)
- [ ] Evaluation 섹션 작성
- [ ] Conclusion 작성
- [ ] 그림/표 정리
- [ ] 논문 최종 교정
- [ ] **8/24 전 제출**

---

## 구현 우선순위

### 반드시 해야 함 (논문 핵심 기여)
1. LLM + RAG → FlowRule 생성
2. Static Validator (스키마 + 기본 충돌 검사)
3. XAI 설명 모듈 (SHAP + LLM 자연어화)

### 하면 더 좋음 (차별점 강화)
4. Digital Twin (Mininet) 검증
5. 자동 재생성 피드백 루프

### 시간이 남으면
6. ONOS 실제 배포 연동
7. Web UI 데모

---

## 기술 스택

| 역할 | 도구 |
|------|------|
| LLM | GPT-4o / Claude (API) |
| RAG | LangChain + FAISS |
| 파이프라인 | LangGraph |
| FlowRule 검증 | Pydantic |
| Digital Twin | Mininet + OVS |
| SDN 컨트롤러 | ONOS |
| XAI | SHAP + LLM |
| 언어 | Python 3.11+ |

---

## 참고 파일

| 파일 | 용도 |
|------|------|
| `notes/study.md` | 개념 학습 로드맵 |
| `notes/papers_analysis.md` | 분석 논문 전체 목록 |
| `resources/ref_*.md` | 논문별 상세 분석 + Related Work 소스 |
| `archive/explainable_sdn_repo_archive.md` | ONOS/Mininet 환경 구축 참고 |
