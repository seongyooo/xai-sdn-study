# 실험 2 — Static Validator 계획

> 작성: 2026-07-13

---

## 목표

LLM이 생성한 FlowRule JSON이 올바른지, 다른 규칙과 충돌하는지 자동 탐지.
NetIntent는 충돌 탐지만 함 → 우리는 **왜 충돌하는지 자연어 설명까지 추가** (차별점).

---

## 사용 데이터

| 파일 | 내용 | 위치 |
|------|------|------|
| `FlowConflict-ONOS.csv` | FlowRule 쌍 74개 + 충돌 여부 + 충돌 유형 | `netintent_baseline/NetIntent/GitHub NetIntent/Datasets/` |

**FlowConflict-ONOS.csv 컬럼:**
- `ONOS Flow Rule 1`: 첫 번째 FlowRule JSON
- `ONOS Flow Rule 2`: 두 번째 FlowRule JSON
- `Conflicting`: Yes / No
- `Type of Conflict`: Shadowing / Redundancy / Correlation / NaN

**데이터 통계 (74쌍):**
- Conflicting Yes: 약 37쌍
- Conflicting No: 약 37쌍
- 충돌 유형: Shadowing (우선순위가 덮음), Redundancy (중복), Correlation (같은 패킷 다른 처리)

---

## 3단계 구성

### Step 1 — JSON 스키마 검증 (Pydantic)

**목적**: LLM이 생성한 FlowRule에 구조적 오류가 있으면 즉시 탐지

**검사 항목:**
```
필수 필드 체크:
  - deviceId 존재 여부
  - selector.criteria 존재 여부
  - priority가 정수인지

타입/형식 체크:
  - deviceId 형식: "of:000000000000000X" (16자리 hex)
  - isPermanent: "true" 문자열
  - ETH_TYPE 값: "0x800", "0x86DD", "0x806" 중 하나
  - IP 형식: "10.0.0.1/32" (CIDR 표기)

존재하지 않는 필드 탐지 (LLM 환각):
  - type이 OUTPUT/DROP/QUEUE/L2MODIFICATION 외의 값
  - criteria type이 정의되지 않은 값
```

**평가 방법:**
- 의도적으로 망가뜨린 FlowRule 10개 생성 → 탐지율 측정

---

### Step 2 — 충돌 탐지

**목적**: FlowRule 2개가 서로 충돌하는지 탐지 + 유형 분류

**충돌 유형 정의:**
| 유형 | 설명 | 탐지 조건 |
|------|------|-----------|
| Shadowing | 상위 priority 규칙이 하위를 완전히 가림 | priority 다름 + match 포함관계 |
| Redundancy | 동일한 규칙 중복 | priority 같음 + match 같음 + action 같음 |
| Correlation | 같은 패킷에 서로 다른 action | match 겹침 + action 다름 |

**구현 방법: LLM 기반 (NetIntent 방식 재현)**
```
입력: FlowRule1 + FlowRule2
프롬프트: "두 ONOS FlowRule이 충돌하는지 분석하라. 
           Shadowing/Redundancy/Correlation 유형으로 분류하거나 충돌 없음으로 답하라."
출력: {"conflicting": true/false, "type": "Shadowing" | "Redundancy" | "Correlation" | null}
```

**평가 지표:**
- Accuracy, Precision, Recall, F1 (FlowConflict-ONOS 74쌍 기준)
- NetIntent 논문 수치와 비교

---

### Step 3 — 충돌 이유 설명 (우리 차별점)

**목적**: 충돌이 탐지된 경우 왜 충돌하는지 자연어로 설명 생성

**입력**: FlowRule1 + FlowRule2 + 충돌 유형
**출력**: 자연어 설명

**출력 예시:**
```
[충돌 탐지 보고서]

충돌 유형: Shadowing

설명:
FlowRule 1 (priority 200)이 FlowRule 2 (priority 102)를 가립니다.
두 규칙 모두 목적지 IP 10.0.0.4로 가는 트래픽을 매치하지만,
FlowRule 1의 우선순위(200)가 높아 항상 먼저 적용됩니다.
결과적으로 FlowRule 2 (port 4로 전달)는 실제로 동작하지 않습니다.

권장 조치:
FlowRule 2의 priority를 200보다 높게 설정하거나,
match 조건을 더 구체적으로 수정하세요.
```

**평가 방법:**
- 충돌 탐지된 케이스에 대해 설명 생성
- 사람이 Usefulness(유용성) / Correctness(정확성) 1~5점으로 평가

---

## 파이프라인 연결

```
[실험 1 출력] FlowRule JSON
        ↓
[Step 1] Pydantic 스키마 검증
    오류 있음 → 오류 메시지 → LLM 재생성 (최대 3회)
    오류 없음 ↓
[Step 2] 기존 규칙들과 충돌 탐지
    충돌 있음 → [Step 3] 충돌 이유 설명 생성
    충돌 없음 ↓
[다음 단계] Digital Twin or ONOS 배포
```

---

## 코드 구조

```
experiments/static_validator/
  PLAN.md              ← 이 파일
  validator.py         ← Step 1: Pydantic 스키마 검증
  conflict_detector.py ← Step 2: 충돌 탐지 실험
  explainer.py         ← Step 3: 충돌 설명 생성
  experiment.py        ← 전체 실행 엔트리포인트
  results/             ← 실험 결과 저장
  README.md            ← 설치/실행 방법
```

---

## 예상 결과 (논문 활용)

| 구성 | 논문 섹션 | 주장 |
|------|-----------|------|
| Step 1 정확도 | Evaluation | "Pydantic 검증으로 LLM 환각을 X% 탐지" |
| Step 2 F1 | Evaluation | "NetIntent 충돌 탐지 F1 XX% → 우리 XX%" |
| Step 3 평가 점수 | Evaluation | "충돌 설명 Usefulness 평균 X.X/5" |

---

## 실행 방법 (구현 후)

```bash
cd experiments/static_validator
set GOOGLE_API_KEY=...

# 전체 실험
python experiment.py

# 단계별 실행
set RUN_STEPS=1   # 스키마 검증만
set RUN_STEPS=2   # 충돌 탐지만
set RUN_STEPS=3   # 충돌 설명만
python experiment.py
```
