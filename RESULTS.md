# 실험 결과 요약

> 실험 기간: 2026-07-13 ~ 2026-07-15
> 비교 모델: `gemma4:e4b`, `qwen3:8b`
> 참조 모델: `gemini-3.1-flash-lite` (이전 실험, RAG 결과만 존재)
> 엔드포인트: `https://ollama.jangmyun.dev/v1`
> 임베딩 모델: `nomic-embed-text`

---

## 실험 1 — Intent-to-FlowRule 생성 (LLM + RAG)

데이터셋: IBNBench Intent2Flow-ONOS (50쌍, 25 train / 25 test)

### 모델별 정확도

| 방식 | gemma4:e4b | qwen3:8b | Gemini (참조) |
|------|:----------:|:--------:|:-------------:|
| Zero-shot | 40.0% (10/25) | 28.0% (7/25) | 96.0% (24/25) |
| Few-shot k=3 | 52.0% (13/25) | 48.0% (12/25) | 92.0% (23/25) |
| Few-shot k=6 | 72.0% (18/25) | 56.0% (14/25) | 84.0% (21/25) |
| **RAG k=3** | **84.0% (21/25)** | **84.0% (21/25)** | **96.0% (24/25)** |
| **RAG k=6** | **88.0% (22/25)** | **84.0% (21/25)** | **96.0% (24/25)** |

> Gemini RAG 결과는 이전 실험(Gemini API 기반) 수치로, 직접 비교 시 모델 규모 차이를 고려해야 함.

### 주요 관찰

**1. RAG가 모델 격차를 수렴시킴**
- Zero-shot 격차: gemma4 vs qwen3 = **12%p**
- RAG k=3 격차: gemma4 vs qwen3 = **0%p** (동률 84%)
- RAG가 소형 모델의 SDN 도메인 지식 부족을 효과적으로 보완

**2. RAG vs Few-shot 안정성**

| | k=3 → k=6 변화 |
|--|----------------|
| Few-shot (gemma4) | 52% → 72% (+20%p) |
| Few-shot (qwen3) | 48% → 56% (+8%p) |
| RAG (gemma4) | 84% → 88% (+4%p) |
| RAG (qwen3) | 84% → 84% (0%p) |

- qwen3:8b RAG는 k 증가에도 안정적 유지
- gemma4:e4b는 예시 수 증가에 더 민감하게 반응 (few-shot +20%p)

**3. 두 모델 공통 고정 FAIL 샘플 (RAG에서도 실패)**

| 인텐트 | 원인 추정 |
|--------|----------|
| `"Forward traffic entering on port 1 of switch 2 to port 2."` | 데이터셋 레이블 오류 가능성 |
| `"Route HTTP traffic originating from 192.168.1.2 on port 1 of switch 4..."` | VLAN+QoS 복합 인텐트, 비표준 패턴 |
| `"Route TCP traffic entering switch 1 on port 1 and targeted at port 80..."` | 복합 매칭 조건 |

---

## 실험 2 — Static Validator (충돌 탐지 + 스키마 검증)

> ⏳ gemma4:e4b, qwen3:8b 모델 실험 진행 예정

참조용 이전 실험(Gemini 기반) 결과:

| Step | 내용 | 정확도 |
|------|------|--------|
| Step 1: 스키마 검증 | Pydantic 기반, LLM 미사용 | 100% (10/10) |
| Step 2: 충돌 탐지 | FlowConflict-ONOS 74쌍 | 98.6% (73/74) |
| Step 3: 충돌 설명 | why / impact / remedy 생성 | 정성 평가 |

---

## 실험 3 — Digital Twin (Mininet 네트워크 검증)

LLM 미사용 (모델 무관). Static Validator 통과 FlowRule을 Mininet에 배포 후 검증.

| 검증 항목 | 결과 |
|----------|------|
| 4개 스위치 ONOS 등록 | PASS |
| 기본 연결 (h1→h4) | PASS |
| DROP 룰 적용 후 차단 (h1→h4) | PASS |
| 무관 트래픽 영향 없음 (h2→h3) | PASS |
| DROP 룰 제거 후 복구 (h1→h4) | PASS |
| **종합** | **5/5 PASS** |

---

## 전체 파이프라인 요약

```
자연어 인텐트
    ↓ [실험 1] RAG k=3~6
FlowRule JSON 생성 (gemma4: 84~88%, qwen3: 84%)
    ↓ [실험 2] Static Validator
스키마 검증 + 충돌 탐지 (98.6% 정확도)
    ↓ [실험 3] Digital Twin
Mininet 네트워크 동작 검증 (5/5 PASS)
```

---

## 결과 파일 위치

```
experiments/1_netintent_baseline/results/
  summary_gemma4-e4b_1783997902.csv
  details_gemma4-e4b_1783997902.json
  summary_qwen3-8b_1784013187.csv
  details_qwen3-8b_1784013187.json

experiments/2_static_validator/results/
  step1_schema_*.json
  step2_conflict_*.json
  step3_explanation_*.json

experiments/3_digital_twin/results/
  digital_twin_1783939831.json
```
