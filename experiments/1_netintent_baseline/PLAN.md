# 실험 1 — LLM + RAG FlowRule 생성 계획

> 작성: 2026-07-13

---

## 목표

자연어 네트워크 인텐트를 ONOS FlowRule JSON으로 변환하는 3가지 방식을 비교.
NetIntent 논문(가장 유사한 선행 연구)의 Few-shot 방식을 재현하고,
우리 방식인 RAG의 우수성을 수치로 증명.

---

## 선행 연구: NetIntent

NetIntent (Hossain & Aljoby, IEEE OJCOMS 2025)는 동일한 태스크를 수행하는 가장 가까운 선행 연구.

| 항목 | NetIntent | 우리 |
|------|-----------|------|
| 인텐트 → FlowRule | ✓ | ✓ |
| 예시 제공 방식 | Few-shot (고정 예시) | RAG (유사 예시 동적 검색) |
| RAG | ✗ | ✓ |
| Digital Twin | ✗ | ✓ (실험 3) |
| XAI 설명 | ✗ | ✓ (실험 4) |

---

## 데이터셋: IBNBench Intent2Flow-ONOS

NetIntent 논문이 공개한 벤치마크 데이터셋.

- **총 50쌍**: (자연어 인텐트, ONOS FlowRule JSON 정답)
- **split**: train 25개 / test 25개 (50/50, random_state=42 — NetIntent와 동일)
- **출처**: github.com/Muhammadkamrul/NetIntent

**샘플 예시:**
```
instruction: "In switch 1, forward TCP traffic on port 80 destined for
              10.0.0.3 through port 2."

output: {"flows": [{"priority": 110, "deviceId": "of:0000000000000001",
          "treatment": {"instructions": [{"type": "OUTPUT", "port": "2"}]},
          "selector": {"criteria": [{"type": "TCP_DST", "tcpPort": 80},
                                    {"type": "IPV4_DST", "ip": "10.0.0.3/32"},
                                    ...]}}]}
```

---

## 3가지 실험 방식

### Step 1 — Zero-shot (베이스라인)
예시 없이 LLM에게 바로 질문.
시스템 프롬프트에 ONOS JSON 형식 설명만 포함.

```
[System] ONOS FlowRule 형식 설명 (필드 목록, 예시 구조)
[User]   "In switch 1, forward TCP traffic on port 80..."
[LLM]    → FlowRule JSON 생성
```

### Step 2 — Few-shot (NetIntent 방식 재현)
train set에서 고정된 k개 예시를 시스템 프롬프트에 포함.
k=3, k=6 각각 테스트.

```
[System] ONOS FlowRule 형식 설명
         + 예시 1: Input: ... / Output: ...
         + 예시 2: Input: ... / Output: ...
         + 예시 3: Input: ... / Output: ...
[User]   "In switch 1, forward TCP traffic on port 80..."
[LLM]    → FlowRule JSON 생성
```

### Step 3 — RAG (우리 방식)
train set 전체를 임베딩 → FAISS 인덱스 구축.
각 테스트 인텐트마다 의미적으로 가장 유사한 k개 예시를 동적 검색.
k=3, k=6 각각 테스트.

```
[임베딩] train 25개 → gemini-embedding-001 → FAISS 저장

[실험시] 테스트 인텐트 → 임베딩 → FAISS 검색 → 유사 k개 추출
[System] ONOS FlowRule 형식 설명
         + 유사 예시 k개 (질문마다 다름)
[User]   "In switch 1, forward TCP traffic on port 80..."
[LLM]    → FlowRule JSON 생성
```

**Few-shot과 RAG의 차이:**
- Few-shot: 어떤 질문이 들어와도 항상 같은 예시 k개 제공
- RAG: 질문과 가장 비슷한 예시 k개를 실시간 검색해서 제공

---

## 평가 기준

NetIntent 원본 평가 함수(`compare_onos_json`) 사용:

| 필드 | 평가 방식 |
|------|-----------|
| `priority` | **무시** (LLM마다 다르게 생성해도 허용) |
| `deviceId` | **정확히 일치** |
| `isPermanent` | **정확히 일치** |
| `treatment` | **정확히 일치** |
| `selector` | **정확히 일치** |
| hex 값 | 정규화: `0x0800` == `0x800` |
| 포트 타입 | 정규화: `"2"` == `2` |
| criteria 순서 | **무시** (순서 달라도 OK) |

즉, **"FlowRule의 핵심 의미가 정답과 같은가"** 를 측정.

---

## 사용 모델

| 용도 | 모델 |
|------|------|
| FlowRule 생성 | `gemini-3.1-flash-lite` |
| 임베딩 (RAG) | `gemini-embedding-001` |
| API | Google Gemini (무료 티어) |

---

## 실행 방법

```bash
cd experiments/netintent_baseline
set GOOGLE_API_KEY=...

# 전체 실험 (Step 1~3)
python experiment.py

# 특정 step만
set RUN_STEPS=1        # Zero-shot만
set RUN_STEPS=2        # Few-shot만
set RUN_STEPS=3        # RAG만
set RUN_STEPS=1,3      # Zero-shot + RAG
python experiment.py
```

---

## 예상 결과 및 논문 활용

**예상 패턴:**
- Zero-shot: LLM 성능에 따라 다름
- Few-shot k 증가: 예시가 많아질수록 성능 향상 or 하락 (프롬프트 길이 문제)
- RAG: k 증가에도 성능 유지 (항상 관련 예시만 검색하기 때문)

**논문에서 주장할 내용:**
> "RAG 기반 동적 예시 검색은 고정 예시(Few-shot) 대비 k가 늘어도 성능이 안정적으로 유지된다."
