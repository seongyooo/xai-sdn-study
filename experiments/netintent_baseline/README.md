# NetIntent Baseline Experiment

IBNBench Intent2Flow-ONOS 데이터셋으로 3가지 방식(Zero-shot / Few-shot / RAG)의 FlowRule 생성 정확도를 비교하는 실험.

---

## 실험 개요

**목표**: 자연어 네트워크 인텐트 → ONOS FlowRule JSON 변환 정확도 측정

**비교 방식**:
| 방식 | 설명 |
|------|------|
| Zero-shot | 예시 없이 LLM에게 바로 질문 |
| Few-shot (k=3,6) | 고정된 k개 예시를 프롬프트에 포함 (NetIntent 방식) |
| RAG (k=3,6) | 질문과 의미적으로 유사한 k개 예시를 자동 검색해서 포함 (우리 방식) |

**데이터셋**: IBNBench — Intent2Flow-ONOS (50쌍, 50/50 split)

---

## 환경 요구사항

- Python 3.12+
- Miniconda 또는 pip 사용 가능한 환경
- Google Gemini API 키 ([aistudio.google.com](https://aistudio.google.com) 에서 무료 발급)

---

## 설치 방법

### 1. 저장소 클론 (또는 파일 다운로드)

```bash
git clone <this_repo>
cd experiments/netintent_baseline
```

### 2. 패키지 설치

```bash
pip install google-genai==2.11.0
pip install faiss-cpu==1.14.3
pip install pandas scikit-learn numpy
pip install langchain langchain-community
```

한 줄로:
```bash
pip install google-genai faiss-cpu pandas scikit-learn numpy langchain langchain-community
```

### 3. IBNBench 데이터셋 다운로드

NetIntent 공식 GitHub에서 데이터셋을 가져옴:

```bash
git clone https://github.com/Muhammadkamrul/NetIntent.git
```

클론 후 폴더 구조:
```
netintent_baseline/
  NetIntent/
    GitHub NetIntent/
      Datasets/
        Intent2Flow-ONOS.csv    ← 이번 실험에 사용
        FlowConflict-ONOS.csv   ← 다음 실험(Static Validator)에 사용
        ...
```

### 4. API 키 설정

[aistudio.google.com](https://aistudio.google.com) → 로그인 → "Get API key" → 키 복사

```bash
# Windows CMD
set GOOGLE_API_KEY=여기에_키_입력

# Windows PowerShell
$env:GOOGLE_API_KEY="여기에_키_입력"

# Mac/Linux
export GOOGLE_API_KEY="여기에_키_입력"
```

---

## 실행 방법

### 전체 실험 (Step 1~3, 약 15분 소요)

```bash
python experiment.py
```

### 특정 Step만 실행

```bash
# Step 1만 (Zero-shot, 약 2분)
set RUN_STEPS=1
python experiment.py

# Step 2만 (Few-shot, 약 5분)
set RUN_STEPS=2
python experiment.py

# Step 3만 (RAG, 약 7분)
set RUN_STEPS=3
python experiment.py

# Step 1,3만
set RUN_STEPS=1,3
python experiment.py
```

---

## 결과 확인

실험 완료 후 `results/` 폴더에 저장됨:

```
results/
  summary_XXXXXXXXXX.csv    ← 방식별 정확도 요약
  details_XXXXXXXXXX.json   ← 샘플별 입력/출력/정답 상세 기록
```

**summary 예시:**
```
step        accuracy  correct  total
zero_shot     96.0       24     25
few_shot_k3   92.0       23     25
few_shot_k6   84.0       21     25
rag_k3        96.0       24     25
rag_k6        96.0       24     25
```

---

## 사용 모델

| 용도 | 모델 |
|------|------|
| FlowRule 생성 | `gemini-3.1-flash-lite` |
| 임베딩 (RAG용) | `gemini-embedding-001` |

`experiment.py` 상단의 `MODEL` 변수를 수정해서 다른 모델로 바꿀 수 있음:

```python
MODEL = "gemini-3.1-flash-lite"   # 이 줄 수정
```

---

## 평가 기준

NetIntent 논문 원본 평가 함수(`compare_onos_json`) 사용:

- **일치해야 하는 필드**: `deviceId`, `isPermanent`, `treatment`, `selector`
- **무시하는 필드**: `priority` (LLM마다 다르게 생성해도 허용)
- hex 정규화: `0x0800` == `0x800` 동일 처리
- 포트 타입 정규화: `"2"` == `2` 동일 처리
- criteria 순서 무시

---

## 실험 결과 (2026-07-13 기준)

| 방식 | 정확도 | 정답/전체 |
|------|--------|-----------|
| Zero-shot | **96.0%** | 24/25 |
| Few-shot k=3 | 92.0% | 23/25 |
| Few-shot k=6 | 84.0% | 21/25 |
| RAG k=3 | **96.0%** | 24/25 |
| RAG k=6 | **96.0%** | 24/25 |

**핵심 결과**: RAG는 k가 늘어도 96% 유지. Few-shot은 k=6에서 84%로 하락.

---

## 데이터셋 출처 및 인용

IBNBench 데이터셋 사용 시 아래 논문 인용 필요:

```bibtex
@article{hossain2025netintent,
  title={NetIntent: Leveraging Large Language Models for End-to-End Intent-Based SDN Automation},
  author={Hossain, Md. Kamrul and Aljoby, Walid},
  journal={IEEE Open Journal of the Communications Society},
  volume={6},
  year={2025},
  doi={10.1109/OJCOMS.2025.3642642}
}
```

---

## 파일 구조

```
netintent_baseline/
  experiment.py          ← 메인 실험 코드
  README.md              ← 이 파일
  NetIntent/             ← IBNBench 데이터셋 (git clone)
  data/                  ← 추가 데이터 저장용 (현재 비어있음)
  results/               ← 실험 결과 저장
```
