# NetIntent 논문 상세 분석

**제목:** NetIntent: Leveraging Large Language Models for End-to-End Intent-Based SDN Automation
**저자:** Md. Kamrul Hossain, Walid Aljoby (KFUPM, 사우디아라비아)
**출처:** IEEE Open Journal of Communications Society, Vol. 6, 2025
**DOI:** 10.1109/OJCOMS.2025.3642642
**접수:** 2025-11-13 / 게재:** 2025-12-10

---

## 1. 논문이 풀려는 문제

### 기존 IBN의 한계

SDN은 제어 평면과 데이터 평면을 분리해 중앙집중 제어를 가능하게 했지만, 여전히 **사람이 고수준 정책을 저수준 FlowRule로 직접 변환**해야 하는 문제가 남아 있었다.

Intent-Based Networking(IBN)은 이 문제를 해결하려 등장했는데, 기존 IBN 구현체들은:
- 운영자가 NSD / JSON / XML 같은 **구조화된 형식으로 인텐트를 표현**해야 했음
- YANG 데이터 모델 문법을 알아야 했음 → 기술적 장벽
- **Rule-based translator** 방식 → 언어 다양성에 취약

### 이 논문이 주장하는 해결책

> "LLM을 활용해 자연어 인텐트 → FlowRule → 충돌 탐지 → 배포 → 보증까지 전체 IBN 라이프사이클을 자동화할 수 있다"

---

## 2. 논문의 두 가지 핵심 기여

### 기여 1 — IBNBench (벤치마크 데이터셋)

33개 오픈소스 LLM을 평가하기 위한 최초의 IBN 전용 벤치마크. 총 8개 데이터셋.

| 데이터셋 종류 | 컨트롤러 | 내용 |
|---|---|---|
| Intent2Flow-ODL | OpenDaylight | 자연어 인텐트 → FlowRule JSON 50쌍 |
| Intent2Flow-ONOS | ONOS | 자연어 인텐트 → FlowRule JSON 50쌍 |
| Intent2Flow-Ryu | Ryu | 자연어 인텐트 → FlowRule JSON 50쌍 |
| Intent2Flow-Floodlight | Floodlight | 자연어 인텐트 → FlowRule JSON 50쌍 |
| FlowConflict-ODL | OpenDaylight | FlowRule 쌍 60개 + 충돌 레이블 (충돌 19개) |
| FlowConflict-ONOS | ONOS | FlowRule 쌍 74개 + 충돌 레이블 (충돌 27개) |
| FlowConflict-Ryu | Ryu | FlowRule 쌍 50개 + 충돌 레이블 (충돌 30개) |
| FlowConflict-Floodlight | Floodlight | FlowRule 쌍 50개 + 충돌 레이블 (충돌 30개) |

**데이터셋 구성 방법:**
- 다이아몬드 토폴로지 (스위치 4개 s1~s4, 호스트 4개 h1~h4) 기반
- 수동 작성 + LLM 생성 후 수동 검증 + 실제 스위치 배포로 검증
- 인텐트 카테고리: **Forwarding / Security / QoS** 3가지

### 기여 2 — NetIntent 프레임워크

IBN 전체 라이프사이클을 LLM으로 자동화하는 엔드투엔드 시스템.

---

## 3. NetIntent 시스템 설계

### 전체 구조

```
[자연어 인텐트 입력]
        ↓
┌─────────────────────────────────┐
│  Stage 1: Intent Translation    │
│  LLM + Context Examples         │
│  → JSON 검증기                  │
│  → 실패 시 피드백 + 재생성       │
└─────────────────────────────────┘
        ↓ 유효한 FlowRule JSON
┌─────────────────────────────────┐
│  Stage 2: Intent Activation     │
│  LLM 충돌 탐지                  │
│  → 충돌 해결 정책 P             │
│  → SDN 컨트롤러 REST API 배포   │
└─────────────────────────────────┘
        ↓ 배포 완료
┌─────────────────────────────────┐
│  Stage 3: Intent Assurance      │
│  테스트 트래픽 생성              │
│  → Intent Drift 탐지            │
│  → LLM 수정 조치 생성 (폐쇄루프) │
└─────────────────────────────────┘
```

---

### Stage 1 — Intent Translation (의도 변환)

#### (a) Context Example 선택

- **Few-shot 방식**: Intent2Flow 데이터셋의 인텐트-FlowRule 쌍을 프롬프트에 제공
- **Max Marginal Relevance** 선택 전략: 입력과 유사하면서 서로 다양한 예시를 동적 선택
  - 고정 예시(Fixed Few-shot)가 아님 → **입력마다 가장 관련 높은 예시를 동적으로 검색**
  - k가 늘어나면 컨텍스트 길이↑, 응답 시간↑ → 트레이드오프 존재

#### (b) 프롬프트 구조 (4부분)

| 부분 | 내용 |
|------|------|
| 일반 지침 | "자연어 인텐트를 ONOS FlowRule JSON으로 변환하라. JSON만 출력하라." |
| 출력 템플릿 | 컨트롤러별 JSON 스키마 (필수/선택 필드 명시) |
| Context 예시 | 런타임에 동적 삽입 |
| 사용자 인텐트 | 실제 운영자 입력 |

- QoS 인텐트용 별도 슬라이싱 프롬프트 존재 (switch_id, queue_id, port_id 추출)

#### (c) Multi-LLM 조율

- 여러 LLM을 **성능 순위**에 따라 나열
- 상위 LLM이 실패하면 컨텍스트 예시 수 증가 → 그래도 실패하면 다음 LLM으로 교체
- 모든 LLM 실패 시 → 운영자에게 수동 해결 요청

#### (d) JSON 검증기 (LLM 아닌 프로그래밍 방식)

- 컨트롤러별 8가지 문법 규칙 로드
- 구조적/의미적 오류 탐지 → 오류 위치 포함 피드백 생성
- 검증 통과할 때까지 LLM 재호출 반복

**Algorithm 1 요약:**
```
for each LLM Mi:
    while x <= max_context:
        생성 → 검증 → 유효하면 return
        실패하면: x 증가, 오류 피드백으로 재프롬프트
    end while
return 수동 해결 요청
```

---

### Stage 2 — Intent Activation (의도 활성화)

#### (a) 충돌 탐지

- **단일 LLM** 사용 (Translation과 달리)
  - 이유: 잘 설계된 프롬프트 하나로 충분하다는 벤치마크 결과
- 기존 FlowRule들(ODL: Configuration Data Store, ONOS: FlowRuleStore)과 새 규칙 비교
- 충돌 조건: **매치 기준이 겹침 AND 액션이 다름**
- **우선순위(Priority)는 충돌 판단에서 제외** → 배포 시점에 우선순위로 결정하기 때문. 잘못된 우선순위를 기준으로 충돌 판단하면 위양성(false positive) 발생 가능

#### 6가지 충돌 유형 (논문 Table 2 기반)

| 유형 | 설명 |
|------|------|
| Redundancy (중복) | 특정 규칙이 더 일반적인 규칙에 완전히 포함되고 같은 액션 |
| Shadowing (가림) | 우선순위 높은 일반 규칙이 구체적 규칙을 다른 액션으로 가림 |
| Generalization (일반화) | 우선순위 높은 구체 규칙이 더 넓은 규칙과 액션 충돌 |
| Correlation (상관) | 매치가 부분 겹침 + 액션 다름 (포함관계 없음) |
| Overlap (중첩) | 주소 공간이 교차하지만 같은 액션 (문제는 아님) |
| Imbrication (혼재) | MAC 계층에서는 겹치지만 IP 계층에서는 안 겹침 (크로스레이어 모호성) |

#### (b) 충돌 해결 정책 P

충돌 감지 시 자동으로 어느 규칙을 우선할지 결정하는 **결정론적 규칙 기반 정책**:

1. **유형 우선순위**: Security > QoS > Forwarding
2. **구체성(Specificity)**: 매치 필드 수가 많을수록 우선 (/32 IP는 +1.0 추가)
3. **Priority 값**: 위 두 기준이 같으면 priority 값이 높은 쪽 선택
4. 결정 불가 시 → 운영자에게 상세 리포트 전달

#### (c) FlowRule 설치

- ODL: RESTCONF API (PUT)
- ONOS: FlowRuleService REST API (POST)
- Ryu: REST API
- Floodlight: FlowManager POST API
- 설치 후 배포 확인: ODL Operational Data Store / ONOS FlowRuleStore에서 존재 여부 검증
- IntentStore 파일에 인텐트 + FlowRule + 메타데이터 저장 (향후 보증 단계에서 활용)

---

### Stage 3 — Intent Assurance (의도 보증)

**목적**: 배포된 FlowRule이 실제 데이터 평면에서 의도한 대로 동작하는지 **지속적으로 검증**

#### (a) 테스트 트래픽 생성 (TestTrafficSpec)

인텐트 유형별로 다른 트래픽 사용:

| 인텐트 유형 | 사용 트래픽 | 검증 기준 |
|---|---|---|
| Forwarding | ICMP ping | S.packet-count ≥ ExpectedPacketCount |
| Security (drop) | ICMP ping | packet-count 증가 + 실제 drop 동작 확인 |
| QoS | iperf (TCP) | B ≥ α × Bt AND \|Rmeasured - Rt\| ≤ ε |

#### (b) Intent Drift 탐지

- Sfinal - Sinitial = ΔS (트래픽 전후 통계 차이)
- 기대치와 ΔS 비교 → 불일치 시 LLM에 수정 조치 요청
- 규칙이 없어지면 IntentStore에서 재설치

#### (c) 수정 조치 생성 (LLM 기반)

LLM에게 컨텍스트 제공 (인텐트, FlowRule, 편차 지표, 컨트롤러 정보) → 수정 조치 순위 리스트 생성 → 순서대로 실행 → 다시 검증 → 실패하면 이전 결과를 프롬프트에 추가해 반복

**Algorithm 3 (Closed-Loop Assurance) 요약:**
```
for attempt = 1 to MaxAttempts:
    FlowRule 존재 확인 → 없으면 재설치
    Sinitial 수집 → 테스트 트래픽 생성 → Sfinal 수집
    인텐트 유형에 따라 ΔS 검증
    실패 → LLM에 수정 조치 요청 → 실행 → 반복
실패 시 운영자 에스컬레이션
```

---

## 4. 벤치마킹 실험 결과

### 4-1. 인텐트 번역 (Intent Translation)

**핵심 발견:**

| 관찰 | 내용 |
|------|------|
| 대형 모델 성능 | QwQ-fusion:32b, Command-r:35b → 99~100% (구조화된 태스크에서) |
| 중형 모델 성능 | Codellama:7b, Dolphin-Mistral:7b → 컨텍스트 예시 추가 시 최대 +30% |
| 70B 모델 한계 | Codellama:70b, Llama2:70b는 중형 모델 대비 미미한 향상 + 훨씬 높은 비용 |
| 컨텍스트 효과 | k=0→9로 늘릴 때 중형 모델에서 효과 가장 큼 |
| 포화 효과 | 대형 모델(QwQ)은 컨텍스트 많아져도 추가 향상 미미 |
| ONOS vs ODL | ONOS는 제로샷 성능 더 높음 (스키마 단순, 사전학습 데이터와 유사), ODL은 컨텍스트 추가 시 역전 |

**ONOS 최고 성능 모델:**
| Context | LLM | Accuracy |
|---------|-----|----------|
| 0 | Codestral:22b | 96% |
| 1 | Codestral:22b | 96% |
| 3 | Codestral:22b | 100% |
| 6~9 | Codestral:22b + Command-r:35b + QwQ계열 | 100% |

### 4-2. 충돌 탐지 (Conflict Detection)

**FlowConflict-ONOS (74쌍, 충돌 27개):**

| 모델 | Accuracy | F1 | 특징 |
|------|----------|-----|------|
| qwq-fusion:32b | 89% | 0.85 | 최고 균형 성능 |
| qwq-abliterated:32b | 84% | 0.78 | 낮은 FP |
| gemma2:27b / qwq:32b | 82% | - | 완벽한 정밀도(FP=0)지만 재현율↓(FN=13) |
| codellama:7b, llama2:7b 등 | ~36% | - | 모든 쌍을 충돌로 예측 (FPR=100%) |

**Rule-based NLP 베이스라인과 비교:**
- 규칙 기반 번역: 56.0% 의미 정확도 (Intent2Flow-ONOS)
- 규칙 기반 충돌 탐지: 89.19% 정확도, FP=0 → 신뢰성 높지만 확장 어려움

### 4-3. 엔드투엔드 지연 시간

NetIntent ONOS 기준 (선택된 LLM: 번역=Codestral:22b, 충돌탐지=QwQ:32b):

- 인텐트 → 배포 확인까지 총 **20~35초**
- LLM 추론 시간(번역 + 충돌탐지)이 대부분을 차지
- 실시간 네트워크 변경에는 부적합 → **인간 참여 정책 업데이트(Non-RT RIC 수준)에는 적합**

---

## 5. 한계점 (논문이 직접 인정)

| 한계 | 내용 |
|------|------|
| 벤치마크 범위 | Forwarding / Security / QoS만 다룸. Service Function Chaining, 동적 경로 최적화 미포함 |
| 파인튜닝 없음 | 사전학습 모델만 사용. 파인튜닝 시 성능 향상 예상 |
| Semantic Drift 미지원 | 사용자가 명시하지 않은 의도(오래된 규칙)의 의미론적 드리프트 탐지 불가 |
| 적대적 인텐트 | 악의적 사용자가 보안 정책을 우회하는 인텐트를 입력할 경우 방어 없음 |
| LLM 편향 | 사전학습 데이터 편향으로 모호한 인텐트를 잘못 해석할 수 있음 |
| Few-shot 편향 | 다양하지 않은 컨텍스트 예시는 LLM 출력을 편향시킬 수 있음 |

---

## 6. 논문이 제안하는 환각(Hallucination) 대응

NetIntent는 **"zero-trust" 원칙**으로 환각을 완화:

1. **1차 방어 (구문적)**: 비-LLM Validator가 잘못된 JSON 구조를 즉시 탐지 → 자동 피드백 루프로 재생성
2. **2차 방어 (의미론적)**: Intent Assurance 모듈이 테스트 트래픽으로 실제 데이터 평면 동작을 검증 → 구문적으로는 맞지만 잘못된 포트로 전달하는 규칙 탐지

---

## 7. 우리 연구와의 관계

### NetIntent가 있는 것 vs 없는 것

| 기능 | NetIntent | 우리 연구 |
|------|-----------|----------|
| 자연어 → FlowRule | ✓ (Few-shot in-context) | ✓ **(RAG 동적 검색)** |
| JSON 스키마 검증 | ✓ (기본 검증) | ✓ **(Pydantic, 환각 탐지까지)** |
| 충돌 탐지 | ✓ (LLM 기반) | ✓ **(LLM 98.6% + Rule-based 97.3%)** |
| 충돌 이유 설명 | **✗** | **✓ (핵심 차별점)** |
| Digital Twin 검증 | **✗** | ✓ (예정) |
| XAI 설명 | **✗** | ✓ (예정) |
| RAG | **✗** | ✓ |

### 우리 논문 포지셔닝에서 핵심 인용 포인트

**1. NetIntent는 충돌이 왜 발생했는지 설명하지 않는다:**
> Section II-B: "current approaches largely lack mechanism to **explain why a conflict occurred**, limiting their ability to clearly indicate underlying causes of conflicts or recommend actionable resolution strategies"

→ 이 문장이 우리 XAI 모듈의 존재 이유. 논문에서 직접 인용 가능.

**2. RAG 없이 Fixed Few-shot만 사용:**
> Section IV-C1a: "we use the strategy called Max Marginal Relevance example selector" (NetIntent도 유사한 전략 사용하지만 RAG와 다름)

→ NetIntent는 Intent2Flow 데이터셋의 고정 쌍을 컨텍스트로 사용 (동적 문서 검색이 아님)
→ 우리는 FAISS 벡터 DB + gemini-embedding으로 도메인 문서까지 검색

**3. 실험에서 사용 가능한 수치:**
- Rule-based NLP 번역: 56.0% (우리 RAG 96.0%와 비교 가능한 베이스라인)
- Rule-based 충돌 탐지: 89.19% (우리 Rule-based 97.3%와 비교)
- NetIntent LLM 충돌 탐지: 논문에서 직접 수치 미공개 → qwq-abliterated:32b 기준 ONOS F1=0.78 (우리 0.985와 비교)

**4. 데이터셋:**
- 우리가 사용한 FlowConflict-ONOS (74쌍)는 이 논문에서 공개한 것
- Intent2Flow-ONOS (50쌍, train 25/test 25)도 동일

### 충돌 탐지 비교 표 (논문 Evaluation 섹션용)

| 방식 | Accuracy | Macro F1 | 설명 가능성 | 비용 |
|------|----------|----------|------------|------|
| Rule-based NLP (NetIntent 베이스라인) | 89.2% | - | 높음 | 없음 |
| LLM-based (NetIntent, qwq-abliterated) | ~84%* | 0.78* | 낮음 | 있음 |
| Rule-based **(우리)** | 97.3% | 0.970 | **완전 투명** | 없음 |
| LLM-based **(우리)** | **98.6%** | **0.985** | 낮음 | 있음 |
| **LLM + 자연어 설명 (우리 차별점)** | **98.6%** | **0.985** | **✓ 자연어 설명** | 있음 |

*NetIntent 논문은 FlowConflict-ONOS에서 qwq-abliterated의 F1=0.78 보고 (Table 22)

---

## 8. 논문 구조 요약

| 섹션 | 내용 |
|------|------|
| I. Introduction | SDN → IBN의 흐름, LLM 활용 가능성, 기존 연구 한계 |
| II. Background | Intent Lifecycle 3단계 개념, 6가지 충돌 유형, Intent Assurance |
| III. IBNBench | 8개 데이터셋 구성 방법, 33개 LLM 선정 기준, 평가 지표 |
| IV. NetIntent Design | 수학적 모델링, 3단계 파이프라인 상세 설계, 알고리즘 |
| V. Experimental Results | LLM 벤치마킹 결과 (번역/충돌), 베이스라인 비교, 엔드투엔드 지연 |
| VI. Limitations | 범위 제한, 파인튜닝 부재, Semantic Drift, 보안 위협 |
| VII. Conclusion | 요약, 오픈소스 공개 |

---

## 9. 기억할 핵심 사실

1. **논문 기여 2가지**: IBNBench(데이터셋) + NetIntent(시스템) — 둘 다 contribution
2. **Intent Translation에서 컨텍스트 예시 수 ≠ RAG**: NetIntent는 Intent2Flow 데이터셋의 페어를 동적으로 선택하는 것이지, 외부 도메인 문서를 검색하는 RAG가 아님
3. **충돌 탐지에서 우선순위(priority) 무시**: 잘못된 priority로 인한 위양성 방지 목적 → 충돌 탐지 후 해결 정책P에서 priority 조정
4. **Rule-based 충돌 탐지 베이스라인**: 89.19% (FlowConflict-ONOS 기준) — 우리 97.3%가 이를 능가
5. **엔드투엔드 시간 20~35초**: 실시간 불가, 정책 업데이트 수준에서는 허용 가능
6. **Intent Assurance는 LLM + 비LLM 혼합**: 트래픽 생성/통계 수집은 비LLM, 수정 조치 생성은 LLM
7. **논문 저자의 다른 논문**: LEAD-Drift (IEEE ICC 2026) — Intent Drift + XAI를 다룬 후속 연구 (동일 저자팀)
