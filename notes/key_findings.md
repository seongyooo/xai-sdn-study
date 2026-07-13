# 핵심 발견 사항 정리

---

## 0. 연구 방향 고려사항

### 현재 방향의 리스크

**리스크 1 — 구현 범위 과다**
- 6주 안에 RAG + Static Validator + Mininet DT + SHAP XAI 전부 구현 시 각각 POC 수준에 그칠 위험

**리스크 2 — XAI가 부록처럼 보일 수 있음**
- 현재 구조에서 XAI는 마지막 레이어 하나 → 심사자가 "SHAP 붙인 것"으로 볼 수 있음

**리스크 3 — NetIntent와 핵심 태스크 겹침**
- Intent→FlowRule + 충돌탐지는 NetIntent가 이미 구현. RAG/DT/XAI가 차별점이어야 함

---

### 발전 방향 3가지

**방향 A — 현재 방향 유지, XAI를 전면으로 (적극 추천)**
- 논문 서사를 "신뢰 가능성(Trustworthy)"으로 재구성
- XAI가 부록이 아닌 존재 이유가 되도록
- 제목 예시: *"신뢰 가능한 LLM 기반 SDN 정책 자동화: 설명 가능성과 Digital Twin 검증을 중심으로"*
- 핵심 문장: *"LLM이 생성한 SDN 정책을 운영자가 신뢰할 수 없는 이유는 블랙박스이기 때문이다. 본 연구는 검증(DT)과 설명(XAI)을 통해 신뢰 가능한 자동화를 달성한다."*

**방향 B — 범위 축소, 완성도 집중 (안전)**
- Digital Twin을 미래 연구로 빼고 `Intent → RAG+LLM → FlowRule → Static Validator → XAI` 만 구현
- 구현 완성도 ↑, XAI 깊이 ↑, 논문 설득력 ↑
- DT는 "향후 연구에서 Mininet DT와 연동 예정"으로 처리

**방향 C — 새 각도: 충돌 탐지 XAI (가장 참신)**
- 현존 논문 중 "FlowRule 충돌이 왜 발생했는지 자연어로 설명"하는 연구 없음
- NetIntent는 충돌 탐지만 하고 설명은 없음
- 범위가 좁아 완성도 높이기 쉬움
- 예시 출력:
  ```
  "두 FlowRule이 충돌하는 이유:
   둘 다 priority 40000에서 dst_ip=10.0.0.2를 매치하지만
   하나는 port 2로 forward, 다른 하나는 drop —
   네트워크는 어떤 규칙을 따를지 결정할 수 없습니다."
  ```

---

### 방향별 비교

| | 방향 A | 방향 B | 방향 C |
|--|--------|--------|--------|
| 6주 현실성 | △ 빡빡 | ✓ 여유 | ✓ 여유 |
| 논문 참신성 | ○ 보통 | ○ 보통 | ★ 높음 |
| KICS 통과 가능성 | ✓ | ✓ | ✓ |
| 구현 완성도 | △ | ✓ | ✓ |

**현실적 추천**: 방향 A + B 절충
- DT는 Mininet pingall 수준으로 간단히 구현 (완성도보다 존재 자체가 중요)
- XAI를 핵심 기여로 전면에
- IBNBench로 NetIntent와 직접 수치 비교

---

> 논문 서베이 과정에서 발견한 중요 인사이트. 논문 작성 및 구현 시 참고.

---

## 1. 가장 중요한 선행 연구 발견

### NetIntent (Hossain & Aljoby, KFUPM, IEEE OJCOMS 2025)
**우리 연구와 가장 겹치는 논문.**

하는 것:
- 자연어 인텐트 → FlowRule JSON (ONOS 포함)
- JSON 검증 + 오류 피드백 재생성 루프
- LLM 기반 충돌 탐지
- Intent Assurance (폐쇄 루프)
- **33개 오픈소스 LLM 벤치마크**

없는 것:
- RAG ✗ (in-context 예시만 사용)
- Digital Twin ✗
- XAI ✗

**→ 우리 논문의 핵심 차별점은 이 3개다.**

---

## 2. 공개 데이터셋 발견 — IBNBench

NetIntent 논문에서 공개한 벤치마크 데이터셋.

| 데이터셋 | 내용 |
|---------|------|
| `Intent2Flow-ONOS` | 자연어 인텐트 → ONOS FlowRule JSON 페어 |
| `FlowConflict-ONOS` | FlowRule 쌍 + 충돌 여부 레이블 |
| `Intent2Flow-ODL/Ryu/Floodlight` | 다른 컨트롤러용 |
| `FlowConflict-ODL/Ryu/Floodlight` | 다른 컨트롤러용 |

**활용 방법:**
- `Intent2Flow-ONOS`: 우리 LLM+RAG 파이프라인 평가에 직접 사용
- `FlowConflict-ONOS`: Static Validator 성능 평가에 사용
- NetIntent 수치와 직접 비교 가능 → 논문 설득력 향상
- 데이터셋 직접 구축 부담 없음

**링크**: https://doi.org/10.1109/OJCOMS.2025.3642642 (supplementary material)

---

## 3. 논문 포지셔닝 전략

### 핵심 문장 (Introduction/Abstract에 사용)
> *"NetIntent [X]는 자연어 인텐트에서 FlowRule 생성과 충돌 탐지를 자동화했지만, 생성된 정책이 실제 네트워크에서 의도한 대로 동작하는지 사전 검증하는 Digital Twin과, 정책 결정 근거를 운영자에게 설명하는 XAI 메커니즘이 없다. 본 연구는 RAG 기반 도메인 지식 주입, Mininet Digital Twin 사전 검증, SHAP+LLM 기반 XAI 설명을 통합하여 신뢰 가능한 SDN 정책 자동화를 달성한다."*

### 차별점 표 (Related Work 섹션용)
| 연구 | Intent→FlowRule | RAG | Static Valid. | Digital Twin | XAI |
|------|:-:|:-:|:-:|:-:|:-:|
| NetIntent (Hossain, 2025) | ✓ | ✗ | △ | ✗ | ✗ |
| VNF Agent (Nam, 2026) | ✗ | ✓ | ✗ | ✓ | ✗ |
| 6G Orchestration (Martins, 2026) | △ | ✓ | ✓ | ✗ | ✗ |
| Intent-LLM (Provvedi, 2026) | ✓ | ✗ | ✗ | ✗ | ✗ |
| Hallucination-Resistant (Hammar, 2026) | ✗ | ✗ | ✓ | ✓ | ✗ |
| **본 연구** | **✓** | **✓** | **✓** | **✓** | **✓** |

---

## 4. 논문에서 인용할 핵심 수치

| 수치 | 출처 | 활용 위치 |
|------|------|-----------|
| GPT-4 단독으로 12%만 실행 가능 | 2509.22834 (NIST) | Introduction — LLM 단독 한계 |
| Context grounding으로 환각 26pp 감소 | 2606.28348 (Martins) | RAG 도입 근거 |
| Agentic 방식 +12% 수정률, -17% 회귀율 | 2606.06212 (ETH Zurich) | Agentic 파이프라인 정당성 |
| SHAP+LLM 설명 Usefulness +12.2% | 2606.10942 (Chalmers) | XAI 모듈 설계 근거 |
| DT 피드백 루프로 복구 시간 -30% | 2602.05279 (Melbourne) | Digital Twin 검증 정당성 |
| 오픈 모델 Agentic 스캐폴딩으로 7× 향상 | 2606.06212 (ETH Zurich) | 오픈 모델 사용 근거 |
| DT로 유해 명령 대부분 제거 가능 | Hong Survey (POSTECH) | DT 필요성 (서베이 인용) |
| 인간 오류가 네트워크 인시던트 80%+ 원인 | Intent-LLM (Provvedi) | 자동화 필요성 |
| LLM 진단 시간 30분 → 3분 단축 | QoEReasoner (CUHK) | LLM 효율성 |

---

## 5. XAI 모듈 설계 방향

### NIST 4원칙 기반 설계 (NISTIR 8312)
우리 XAI가 4원칙을 충족함을 논문에 명시:

| 원칙 | 우리 구현 |
|------|-----------|
| Explanation | SHAP 기여도 + RAG 참조 문서 + LLM 설명 텍스트 |
| Meaningful | 네트워크 운영자 대상 자연어 설명 |
| Explanation Accuracy | SHAP (수학적 기여도, 사후 근사 아님) |
| Knowledge Limits | 검증 실패 시 FlowRule 배포 거부 |

### XAI 출력 형식 (QoEReasoner 참고)
```
[FlowRule 설명 보고서]
1. 생성된 FlowRule 요약
2. 판단 근거
   - 참조한 RAG 문서: [문서명]
   - 핵심 피처 기여도: src_ip(0.42), dst_port(0.31), protocol(0.18)
3. 유사 과거 정책: [정책 예시]
4. Static Validator 결과: 충돌 없음
5. Digital Twin 검증: pingall 100% 성공
```

### 평가 지표 (Chalmers XAI 논문 참고)
- **Usefulness**: 설명이 운영자의 의사결정에 도움이 됐는가 (1-5점)
- **Correctness**: 설명이 실제 FlowRule 생성 이유와 일치하는가 (1-5점)
- **Scope**: 설명이 충분히 포괄적인가 (1-5점)

---

## 6. RAG 설계 방향

### RAG 소스 구성 (2가지 레이어)
```
Layer 1 — 도메인 지식 (정적)
  - ONOS REST API FlowRule 스펙
  - OpenFlow 1.3 match/action 필드 목록
  - IBN 표준 용어집

Layer 2 — 과거 사례 (동적, 지속 갱신)
  - IBNBench Intent2Flow-ONOS 데이터셋 (직접 활용 가능)
  - 자체 수집 인텐트-FlowRule 페어
```

### 필터링 전략 (s10922 참고)
- **Input 필터링**: 인텐트에서 핵심 키워드 추출 → 정밀 검색
- **Output 필터링**: 검색 결과 중 현재 인텐트와 무관한 문서 제거
- 무관한 문서가 포함되면 오히려 성능 저하 (s10922 실험 결과)

---

## 7. Static Validator 설계 방향

### 검증 레이어 (2509.22834 CFG + 2606.06212 Batfish 참고)
```
Layer 1 — JSON 스키마 검증 (Pydantic)
  - 필수 필드 존재 여부
  - 타입/범위 오류
  - 존재하지 않는 액션 타입 → 환각 즉시 탐지

Layer 2 — 의미론적 충돌 탐지
  - 동일 priority + 동일 match 중복
  - DROP 룰이 FORWARD 룰을 무효화
  - 루프 유발 경로 (A→B→A)
  - IBNBench FlowConflict-ONOS로 성능 평가 가능
```

### 피드백 루프
```
검증 실패 → 오류 메시지 구조화 → LLM 재프롬프트
→ 최대 3회 재시도 → 실패 시 운영자에게 에스컬레이션
```

---

## 8. Digital Twin 설계 방향

### Mininet 활용 패턴 (s10922 NDT, ZTN DT 참고)
```
Static Validator 통과
    ↓
Mininet 토폴로지 자동 생성 (실제 네트워크 복제)
    ↓
FlowRule ONOS REST API로 Mininet에 적용
    ↓
트래픽 테스트 자동화 (pingall, iperf)
    ↓
성공 → XAI 설명 생성 → 실제 ONOS 배포
실패 → 에러 로그 추출 → LLM 재생성 (최대 3회)
```

### 검증 시나리오 (IBNBench 활용)
- L2 포워딩: 호스트 간 통신 가능 여부
- L3 라우팅: IP 기반 경로 검증
- ACL: 차단 정책 실제 동작 확인
- QoS: 대역폭 제한 적용 확인

---

## 9. 같은 저자팀 논문 주의

**KFUPM (King Fahd Univ.) — Hossain & Aljoby 팀**:
- NetIntent (IEEE OJCOMS 2025) — IBN 자동화
- LEAD-Drift (IEEE ICC 2026) — Intent Drift + XAI

두 논문이 연결되는 시스템처럼 보임. NetIntent(생성/배포) + LEAD-Drift(모니터링/드리프트 탐지)를 결합한 연구가 없다는 점도 우리 연구의 포지셔닝에 활용 가능.

---

## 10. 구현 시 참고할 오픈소스/도구

| 도구 | 용도 | 참고 논문 |
|------|------|-----------|
| LangGraph | 상태 기반 멀티 에이전트 파이프라인 | 2606.28348 (Martins) |
| FAISS | 벡터 DB (RAG) | 2606.15709 (Fasha) |
| Pydantic | FlowRule JSON 스키마 검증 | 2607.00292 (El Habbouli) |
| SHAP | XAI 피처 기여도 | 2606.10942, 2602.13672 |
| Mininet | Digital Twin 환경 | s10922 (NDT 참고) |
| IBNBench | 평가 데이터셋 | NetIntent (Hossain) |
| ONOS REST API | FlowRule 실제 배포 | NetIntent, Intent-LLM |
