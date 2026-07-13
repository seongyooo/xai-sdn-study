# 실험 계획 및 구현 목록

> 마감: 2026-08-24 (KICS 제7회 한국 인공지능 학술대회)
> 작성: 2026-07-13

---

## 전체 파이프라인

```
자연어 인텐트 (사람이 말로 입력)
        ↓
[실험 1] LLM + RAG → FlowRule JSON 생성     ← 완료
        ↓
[실험 2] Static Validator → 오류/충돌 탐지   ← 다음
        ↓
[실험 3] Mininet Digital Twin → 가상 검증    ← 이후
        ↓
[실험 4] XAI → 결정 근거 자연어 설명         ← 이후
        ↓
ONOS 실제 배포
```

---

## 실험 1 — LLM + RAG (완료)

**폴더**: `experiments/netintent_baseline/`

**무엇을 했나**
- IBNBench Intent2Flow-ONOS 데이터셋 (50쌍) 사용
- Zero-shot / Few-shot / RAG 방식으로 FlowRule 생성 정확도 비교
- 모델: Gemini 3.1 Flash Lite

**결과**
| 방식 | 정확도 |
|------|--------|
| Zero-shot | 96.0% |
| Few-shot k=3 | 92.0% |
| Few-shot k=6 | 84.0% |
| RAG k=3 | **96.0%** |
| RAG k=6 | **96.0%** |

**결론**: RAG가 Few-shot보다 k가 늘어도 성능 유지. NetIntent(Few-shot)보다 안정적.

**논문에서 활용**: "RAG 기반 예시 검색이 고정 예시 대비 일관된 성능을 보임"

---

## 실험 2 — Static Validator (다음 단계)

**폴더**: `experiments/static_validator/` (생성 예정)

**목표**: 생성된 FlowRule이 올바른지, 다른 규칙과 충돌하는지 자동 탐지

### 2-1. JSON 스키마 검증

**사용 데이터**: 실험 1에서 생성된 FlowRule JSON

**구현 내용**
```python
# Pydantic으로 FlowRule 스키마 정의
class FlowRule(BaseModel):
    priority: int
    timeout: int = 0
    isPermanent: str = "true"
    deviceId: str
    treatment: Optional[Treatment]   # 없으면 DROP 규칙
    selector: Selector
```

**검증 항목**
- 필수 필드 존재 여부 (deviceId, selector 등)
- 타입 오류 (priority가 문자열로 들어온 경우 등)
- 존재하지 않는 액션 타입 (LLM 환각 탐지)
- deviceId 형식 (`of:000000000000000X`)

**평가 방법**: 의도적으로 잘못된 FlowRule 생성 → 탐지율 측정

---

### 2-2. 충돌 탐지

**사용 데이터**: IBNBench `FlowConflict-ONOS.csv` (74쌍, 이미 다운로드됨)

```
NetIntent/GitHub NetIntent/Datasets/FlowConflict-ONOS.csv
컬럼: FlowRule1, FlowRule2, Conflicting(Yes/No), Type of Conflict
```

**충돌 유형**
| 유형 | 설명 | 예시 |
|------|------|------|
| Shadowing | 상위 priority가 하위를 완전히 가림 | priority 200이 priority 102를 덮음 |
| Redundancy | 동일한 규칙이 중복 | 같은 match+action이 두 번 |
| Correlation | 두 규칙이 같은 패킷에 서로 다른 처리 | 하나는 FORWARD, 다른 하나는 DROP |

**구현 방법 2가지 비교**
- 방법 A: 규칙 기반 (조건문으로 직접 비교)
- 방법 B: LLM 기반 (NetIntent 방식, 두 FlowRule을 LLM에게 보여주고 판단)

**평가 지표**: FlowConflict-ONOS 74쌍 → Precision, Recall, F1

---

### 2-3. XAI 연계: 충돌 설명 생성 (우리 차별점)

NetIntent는 충돌 탐지만 함. 우리는 **왜 충돌하는지 자연어로 설명**을 추가.

```
입력: FlowRule 1 + FlowRule 2
출력: "두 규칙이 충돌하는 이유:
       FlowRule 1은 priority 200에서 10.0.0.4로 가는 모든 트래픽을 매치하고,
       FlowRule 2는 priority 102에서 같은 목적지를 다른 포트로 전달합니다.
       priority가 높은 FlowRule 1이 FlowRule 2를 완전히 가려(Shadowing) 
       FlowRule 2는 실제로 동작하지 않습니다."
```

**논문에서 활용**: "충돌 탐지 + 자연어 설명 = NetIntent 대비 차별점"

---

## 실험 3 — Mininet Digital Twin

**폴더**: `experiments/digital_twin/` (생성 예정)

**전제 조건**: Linux 또는 WSL2 환경 필요 (Mininet은 Windows 미지원)

**목표**: Static Validator 통과한 FlowRule을 가상 네트워크에서 실제 테스트

### 구현 순서

**Step 1: Mininet 설치 (WSL2)**
```bash
sudo apt-get install mininet
sudo mn --test pingall   # 설치 확인
```

**Step 2: ONOS Docker 실행**
```bash
docker run -d --name onos -p 8181:8181 -p 6653:6653 onosproject/onos:latest
# Web UI: http://localhost:8181/onos/ui (onos/rocks)
```

**Step 3: 토폴로지 자동 생성**
```python
# Python Mininet API로 토폴로지 코드로 생성
from mininet.net import Mininet
from mininet.topo import SingleSwitchTopo

net = Mininet(topo=SingleSwitchTopo(3))
net.start()
net.pingAll()   # 검증
```

**Step 4: FlowRule 자동 적용 + 테스트**
```python
import requests

# ONOS REST API로 FlowRule 배포
def deploy_flowrule(flowrule: dict):
    url = "http://localhost:8181/onos/v1/flows"
    r = requests.post(url, json=flowrule, auth=("onos", "rocks"))
    return r.status_code == 201

# Mininet에서 트래픽 테스트
def test_connectivity(net, src, dst):
    result = src.cmd(f"ping -c 1 {dst.IP()}")
    return "1 received" in result
```

**평가 지표**: pingall 성공률, 의도한 트래픽 제어 동작 여부

**시간이 없으면**: 이 실험은 "향후 연구"로 미루고 논문에 개념만 서술 가능

---

## 실험 4 — XAI 설명 모듈

**폴더**: `experiments/xai_explanation/` (생성 예정)

**목표**: "왜 이 FlowRule이 생성됐는가"를 운영자에게 설명

### 4-1. SHAP 피처 기여도 분석

**문제**: SHAP은 보통 ML 모델(분류기)에 적용. LLM에는 직접 적용 불가.

**우리 접근법**: 인텐트 텍스트의 키워드를 피처로 추출 → 간단한 분류기 학습 → SHAP 적용

```python
# 인텐트 텍스트 → 피처 추출
features = {
    "has_tcp": 1 if "TCP" in intent else 0,
    "has_drop": 1 if "block" in intent or "drop" in intent else 0,
    "has_port": 1 if re.search(r"port \d+", intent) else 0,
    "has_src_ip": 1 if "source" in intent else 0,
    "has_dst_ip": 1 if "destination" in intent or "destined" in intent else 0,
    ...
}

# 학습된 분류기에 SHAP 적용
import shap
explainer = shap.TreeExplainer(classifier)
shap_values = explainer.shap_values(features)
```

**출력**: 각 피처가 FlowRule 생성 결정에 얼마나 기여했는지 수치

---

### 4-2. LLM으로 설명 자연어화

SHAP 수치 + RAG 검색 결과 + Static Validator 결과를 LLM에게 주고 자연어 설명 생성

```
[XAI 설명 보고서]

생성된 FlowRule 요약:
- switch 1에서 10.0.0.3:80으로 가는 TCP 트래픽을 포트 2로 전달

판단 근거:
- 참조한 RAG 예시: "TCP port 80 → OUTPUT port 2" 유사 케이스 3개
- 핵심 피처 기여도:
    dst_ip(0.42) > tcp_port(0.31) > protocol(0.18) > src_ip(0.09)
- 의미: 목적지 IP와 TCP 포트가 이 규칙 결정에 가장 큰 영향

검증 결과:
- Static Validator: 충돌 없음
- Digital Twin: pingall 100% 성공 (해당되는 경우)
```

---

### 4-3. 평가

**평가 방법 (Chalmers XAI 논문 참고)**

설명을 사람에게 보여주고 1-5점으로 평가:
- **Usefulness**: 이 설명이 의사결정에 도움이 됐는가?
- **Correctness**: 설명이 실제 FlowRule 생성 이유와 일치하는가?
- **Clarity**: 설명이 이해하기 쉬운가?

최소 3~5명에게 평가 받으면 논문에 쓸 수 있음.

---

## 전체 일정 (남은 기간 기준)

```
7/13 ~ 7/20  실험 2: Static Validator 구현 + 평가
7/21 ~ 7/27  실험 4: XAI 설명 모듈 구현 + 평가
7/28 ~ 8/3   실험 3: Mininet DT (시간 여유 있을 때)
             + 전체 파이프라인 통합
8/4  ~ 8/10  실험 결과 정리, 표/그래프 작성
8/11 ~ 8/17  논문 작성
8/18 ~ 8/23  교정 및 최종 제출 준비
8/24         제출 마감
```

---

## 논문 차별점 요약 (실험별 근거)

| 우리 기여 | 근거 실험 | NetIntent와 비교 |
|-----------|-----------|-----------------|
| RAG 기반 예시 검색 | 실험 1 | NetIntent는 고정 few-shot |
| 충돌 탐지 + 자연어 설명 | 실험 2-3 | NetIntent는 탐지만, 설명 없음 |
| XAI 설명 보고서 | 실험 4 | NetIntent에 없음 |
| Mininet 사전 검증 | 실험 3 | NetIntent에 없음 |

---

## 참고 파일

| 파일 | 내용 |
|------|------|
| `notes/key_findings.md` | 논문 서베이 핵심 발견, 포지셔닝 전략 |
| `notes/papers_analysis.md` | 분석 논문 18개 전체 목록 |
| `notes/roadmap.md` | 주차별 구현 로드맵 |
| `experiments/netintent_baseline/` | 실험 1 코드 + 결과 |
| `resources/ref_xai.md` | XAI 관련 논문 5개 상세 분석 |
| `resources/ref_sdn_intent.md` | NetIntent 포함 SDN 논문 분석 |
