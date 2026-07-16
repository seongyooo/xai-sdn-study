# 시스템 개선 로드맵

> 작성: 2026-07-15 / 업데이트: 2026-07-16  
> 현재 상태 기준 — 각 Stage별 한계와 개선 방향 정리  
> `sdn_intent-framework` 비교 분석 반영

---

## 전체 구조 현황

```
자연어 인텐트
  → [Stage 1] LLM + RAG → IntentIR
  → [Stage 2] 결정론적 컴파일러 → FlowRule JSON
  → [Stage 3] Rule-based 정적 검증
  → [Stage 4] Digital Twin (Mininet + ONOS)
  → [Stage 5] XAI 설명 생성
  → [Stage 6] ONOS 배포
```

---

## Stage 1 — 인텐트 파싱 + RAG

### 현재 한계

| 항목 | 현재 |
|------|------|
| 지원 action | `forward`, `block`, `qos` 3종 |
| RAG 데이터셋 | Intent2Flow-ONOS.csv (포워딩·보안 위주) |
| IR 필드 | 5-튜플 + QoS 기본 필드 |
| SFC 표현 | 불가 |
| 경로 지정 | 불가 (단일 스위치만) |

### 개선 방향

#### 1-A. IntentIR 확장 (action 추가)

```python
action: Literal["forward", "block", "qos", "sfc", "reroute"]
```

| action | 의미 | 필요 필드 |
|--------|------|-----------|
| `sfc` | Service Function Chaining — VNF 체인 경유 | `service_chain: list[str]` (VNF 목록) |
| `reroute` | 동적 경로 최적화 — 대역폭/지연 기준 경로 변경 | `metric: "bandwidth" \| "latency"`, `min_bw_mbps` |

**SFC 예시 인텐트:**
```
"route traffic from 10.0.0.1 through firewall then IDS then proxy to 10.0.0.4"
```
**IntentIR:**
```json
{
  "action": "sfc",
  "service_chain": ["firewall", "ids", "proxy"],
  "src_ip": "10.0.0.1/32",
  "dst_ip": "10.0.0.4/32"
}
```

**reroute 예시 인텐트:**
```
"optimize path for video traffic from 10.0.0.1 to 10.0.0.4, minimum 50Mbps"
```

#### 1-B. RAG 데이터셋 확장

현재 데이터셋은 포워딩·보안 위주. 추가 필요:

| 카테고리 | 예시 인텐트 | 비고 |
|----------|------------|------|
| SFC | "route through firewall → IDS" | Group Table 필요 |
| 동적 경로 | "minimum latency path to host B" | 경로 계산 필요 |
| 부하 분산 | "load balance HTTP traffic across port 2 and port 3" | ECMP/Group Table |
| 트래픽 미러링 | "mirror all traffic from switch 1 port 1 to port 4" | 모니터링용 |
| Rate Limiting | "limit traffic from 10.0.0.1 to 10Mbps" | Meter Table |

#### 1-C. LLM 프롬프트 개선

- 현재: 단일 JSON 출력 요청
- 개선: action별 분기된 프롬프트 체인
  1. **1차 LLM 호출**: action 분류 (forward / block / qos / sfc / reroute)
  2. **2차 LLM 호출**: action-specific 필드 추출 (각 action마다 다른 프롬프트)
- 장점: LLM이 한번에 모든 필드를 추출할 때보다 정확도 향상

---

## Stage 2 — FlowRule 컴파일러

### 현재 한계

- `forward` → OUTPUT instruction 단순 매핑
- `block` → NOACTION/DROP 단순 매핑
- `qos` → QUEUE instruction 단순 매핑
- 멀티-플로우 생성 불가 (항상 1개 flow)
- Group Table, Meter Table 미지원

### 개선 방향

#### 2-A. SFC 컴파일 (Group Table)

SFC는 OpenFlow의 **Group Table** (type=INDIRECT 또는 SELECT)으로 구현:

```
service_chain: [firewall@s2, ids@s3, proxy@s4]
→ s1에 Group Entry 생성
→ 각 VNF 서비스 스위치에 FlowRule 생성
→ 총 N+1개 flow (chain 길이 + 1)
```

컴파일러가 반환해야 할 구조:
```json
{
  "flows": [...],       // 기존
  "groups": [...]       // 신규: GROUP TABLE entries
}
```

#### 2-B. 동적 경로 최적화 (reroute)

reroute는 컴파일 시점에 경로를 결정해야 함:
1. ONOS Topology API로 현재 링크 상태 조회
2. ONOS Statistics API로 링크별 대역폭/지연 조회
3. Dijkstra / 최단경로 계산
4. 경로상 각 스위치에 FlowRule 생성 (멀티-플로우)

현재 컴파일러는 ONOS를 몰라도 됨 (결정론적). reroute는 예외적으로 런타임 정보가 필요 → **컴파일러에 optional ONOS client 주입** 방식으로 설계.

#### 2-C. Meter Table (Rate Limiting)

```json
{
  "meters": [{
    "deviceId": "of:0000000000000001",
    "unit": "KB_PER_SEC",
    "bands": [{"type": "DROP", "rate": 10240}]
  }]
}
```

---

## Stage 3 — 정적 검증

### 현재 한계

- 5종 충돌 탐지 (Shadowing, Redundancy, Correlation, Imbrication, Generalization)
- 단일 FlowRule 기준 비교
- Group Table, Meter Table 검증 없음
- SFC 체인 유효성 검사 없음

### 개선 방향

#### 3-A. SFC 체인 유효성

```
체크 항목:
- VNF 노드가 ONOS 토폴로지에 존재하는가?
- 체인 경로가 물리적으로 연결되어 있는가?
- 체인 내 루프 없는가?
```

#### 3-B. 우선순위 갭 분석

현재 충돌 탐지는 기존 flow와의 충돌만 탐지. 추가:
- **Priority Gap Warning**: 새 룰의 priority가 기존 룰 사이에 끼어들 때 경고
- **Catch-all 누락 경고**: 특정 트래픽만 처리하는 룰인데 default drop/forward 룰이 없을 때

#### 3-C. Meter / Group 참조 유효성

- 배포 전 Meter가 실제 ONOS에 생성 가능한지 확인
- Group Entry가 참조하는 출력 포트가 존재하는지 확인

---

## Stage 4 — Digital Twin

### 현재 한계 및 핵심 문제

#### 4-A. 검증 정밀도 부족

| 현재 | 개선 필요 |
|------|----------|
| ping (ICMP, pass/fail) | iperf3 (대역폭 측정 Mbps) |
| 연결 여부만 확인 | 실제 트래픽 경로 추적 필요 |
| 단일 pair 테스트 | 복수 flow 동시 테스트 |

**개선: iperf3 기반 대역폭 검증**

```python
def _bw_check(net, src_host, dst_host, min_mbps: float) -> tuple[bool, str]:
    """iperf3로 대역폭 검증"""
    server = net.get(dst_host)
    client = net.get(src_host)
    server.sendCmd("iperf3 -s -1")
    result = client.cmd(f"iperf3 -c {dst_ip} -t 3 -J")
    # JSON 파싱 → bits_per_second 추출
    bw_mbps = parse_iperf_json(result) / 1e6
    return bw_mbps >= min_mbps, f"{bw_mbps:.1f} Mbps (목표: {min_mbps} Mbps)"
```

**개선: OVS 경로 추적**

```python
# OVS에서 실제 패킷이 어떤 flow를 타는지 확인
result = subprocess.run(
    ["ovs-appctl", "ofproto/trace", f"br-{switch}", "in_port=1,ip,ip_src=10.0.0.1"],
    capture_output=True, text=True
)
# "Verdict: drop" 또는 "output:2" 파싱
```

#### 4-B. Rollback 정책 — 핵심 설계 이슈

**현재 방식의 문제:**
```
배포 전 기존 flow 전체 삭제 → 테스트 → (rollback) 다시 삭제
```

**실제 운영 환경에서의 요구:**

| 시나리오 | 올바른 동작 |
|---------|------------|
| 새 차단 룰 추가 | 기존 포워딩 룰 유지한 채 차단 룰 추가 |
| 경로 최적화 룰 변경 | 기존 경로 룰 삭제 후 새 룰 적용 (전환) |
| SFC 체인 삽입 | 기존 직접 경로 룰과 병존 가능한지 검사 필요 |

**개선 방향: 운영자에게 rollback 정책 선택 위임 (XAI 연동)**

```python
class RollbackPolicy(Enum):
    ADDITIVE    = "additive"    # 기존 flow 유지 + 새 flow 추가
    REPLACE     = "replace"     # 동일 priority 기존 flow 삭제 후 교체
    FULL_RESET  = "full_reset"  # 전체 삭제 후 재배포
```

이 선택의 영향을 XAI가 설명해야 함 (아래 Stage 5 참조).

#### 4-C. 토폴로지 다양화

현재: 다이아몬드 4-스위치 하드코딩  
개선: ONOS Topology API에서 실제 토폴로지 읽어서 Mininet 동적 구성

```python
def build_from_onos(client: OnosClient) -> Mininet:
    devices = client.devices()
    links   = client.links()
    hosts   = client.hosts()
    # → Mininet 토폴로지 동적 생성
```

#### 4-D. 검증 항목 확장

| 현재 검증 | 추가 검증 |
|----------|----------|
| baseline_connectivity (ping) | baseline_bandwidth (iperf) |
| intent_check (ping pass/fail) | intent_bandwidth (QoS 룰의 경우 Mbps) |
| regression (h2↔h3 ping) | regression_bandwidth (기존 트래픽 영향) |
| — | path_trace (패킷이 올바른 경로를 경유하는지) |
| — | sfc_chain_check (VNF 체인 순서 검증) |

---

## Stage 5 — XAI 설명 생성

### 현재 한계

- 템플릿 기반 요약 (단순 문자열 조합)
- LLM은 `decision_reason` 1개 필드에만 사용
- Rollback 영향 설명 없음
- 반사실적(counterfactual) 설명 없음
- 확신도(confidence) 지표 없음

### 개선 방향

#### 5-A. Rollback 정책 영향 XAI 설명

운영자가 `RollbackPolicy`를 선택하기 전에 각 정책의 영향을 설명:

```
ADDITIVE 선택 시:
  → 기존 룰 3개가 유지됩니다.
  → 새 차단 룰(priority=50000)이 기존 포워딩 룰(priority=40000)보다
    높은 우선순위로 추가됩니다.
  → 10.0.0.1→10.0.0.4 트래픽만 차단되며 나머지는 영향 없습니다.

REPLACE 선택 시:
  → 동일 priority의 기존 룰 1개가 삭제됩니다.
  → 서비스 중단 없이 교체 가능합니다.
```

#### 5-B. 반사실적 설명 (Counterfactual)

"이 FlowRule이 없었다면 어떻게 됐을까?"를 설명:

```
현재 판정: APPROVE (차단 룰 배포)
반사실적: 이 룰 없이는 10.0.0.1→10.0.0.4 TCP 트래픽이
          현재 설치된 reactive forwarding 룰에 의해 통과됩니다.
→ 보안 정책상 차단이 필요합니다.
```

구현: Digital Twin에서 룰 배포 전 상태(baseline)와 후 상태를 비교하여 diff 생성.

#### 5-C. 확신도(Confidence) 점수

```python
@dataclass
class XAIReport:
    ...
    confidence: float  # 0.0~1.0
    confidence_breakdown: dict  # {"intent_parse": 0.9, "static": 1.0, "twin": 0.8}
```

계산 방법:
- LLM 파싱: `logprobs` 또는 재파싱 일관성으로 측정
- 정적 검증: 충돌 없음=1.0, 경고=0.8, 충돌=0.3
- Digital Twin: PASS=1.0, SKIP=0.7, FAIL=0.0

#### 5-D. 설명 레벨 분리

운영자 역할에 따라 설명 깊이를 다르게:

| 레벨 | 대상 | 내용 |
|------|------|------|
| `brief` | 비전문가 | "차단 룰이 올바르게 작동했습니다. (APPROVE)" |
| `standard` | 일반 운영자 | 현재 수준 (스테이지별 요약) |
| `detailed` | 네트워크 엔지니어 | FlowRule 전체 + 충돌 분석 + 경로 추적 결과 |

---

## Stage 6 — ONOS 배포

### 현재 한계

- 배포 후 상태 모니터링 없음
- 배포 실패 시 자동 rollback 없음
- 단계적(staged) 배포 없음

### 개선 방향

#### 6-A. 배포 후 모니터링

```python
def deploy_and_monitor(self, flowrule: dict, monitor_sec: int = 30) -> DeployResult:
    """배포 후 N초 동안 flow 상태 모니터링"""
    self.deploy(flowrule)
    # 30초간 flow 상태 polling
    # ADDED → PENDING_ADD → ADDED: 정상
    # FAILED: 자동 rollback 트리거
```

#### 6-B. 자동 Rollback

배포 후 flow가 `FAILED` 상태가 되면:
1. 배포한 flow 삭제
2. XAI에 rollback 사실 기록
3. 운영자에게 알림

#### 6-C. Dry-run 모드

실제 ONOS에 배포하지 않고 배포 가능 여부만 확인:
```python
deployer.deploy(flowrule, dry_run=True)
# → {"deployable": True, "estimated_flow_count": 1, "conflicts_with_existing": []}
```

---

## 우선순위 요약

논문 마감(2026-08-24)까지 구현 가능성 기준:

| 우선순위 | 항목 | 난이도 | 논문 기여 |
|---------|------|--------|----------|
| 🔴 높음 | Stage 4 iperf 대역폭 검증 | 중 | Digital Twin 정밀도 향상 |
| 🔴 높음 | Stage 5 Rollback 영향 XAI 설명 | 중 | XAI 차별화 포인트 |
| 🔴 높음 | Stage 1 SFC + reroute action 추가 | 중 | 인텐트 유형 다양화 |
| 🟡 중간 | Stage 5 Confidence 점수 | 중 | 정량 평가 가능 |
| 🟡 중간 | Stage 2 멀티-플로우 (reroute 경로) | 높음 | 경로 최적화 시연 |
| 🟡 중간 | Stage 4 Rollback 정책 선택 | 중 | 운영 현실성 |
| 🟢 낮음 | Stage 4 ONOS 토폴로지 동적 구성 | 높음 | 범용성 향상 |
| 🟢 낮음 | Stage 6 배포 후 모니터링 | 중 | 완성도 |
| 🟢 낮음 | Stage 5 반사실적 설명 | 높음 | XAI 심화 |

---

## 논문 관점에서의 핵심 차별화 포인트

현재 논문이 기존 연구 대비 강조할 수 있는 포인트:

1. **Rollback 정책 XAI 설명**: 기존 연구는 생성·검증만 다루고 "배포 이후"를 다루지 않음
2. **SFC 지원**: IBNBench, NetIntent 등은 단순 forward/block만 평가
3. **Confidence 점수**: 기존 LLM 기반 연구는 정확도만 측정, 확신도는 다루지 않음
4. **iperf 대역폭 검증**: ping 기반 pass/fail보다 정량적인 QoS 검증

이 중 **Rollback 정책 XAI + iperf Digital Twin** 두 가지만 추가해도 논문의 완성도가 크게 올라감.

---

## sdn_intent-framework 비교 분석 — 추가 보완 항목

> `C:\Users\seonl\Desktop\c\2026\summer\sdn_intent-framework` 프로젝트와 비교하여 도출한 격차

### 현재 프로젝트 우위

| 항목 | 현재 프로젝트 | sdn_intent-framework |
|------|-------------|---------------------|
| Digital Twin | ✅ 실제 Mininet+ONOS 동작 | 설정 플래그만 존재 (미구현) |
| 정적 충돌 탐지 | ✅ 5종 구현 | 미구현 |
| ONOS 실배포 | ✅ Stage 6 | 미구현 |
| XAI 설명 생성 | ✅ 실제 생성 | 미구현 |
| Streamlit UI | ✅ 토폴로지 시각화 포함 | 없음 |

### 추가 보완 필요 항목

---

#### [신규] B-1. 인텐트 거부(Rejection) 처리 — 🔴 높음

**현재 문제**: 모호하거나 지원 불가한 인텐트도 무조건 IR 생성 시도. LLM이 잘못된 인텐트를 받으면 엉뚱한 FlowRule이 생성됨.

**참조**: `sdn_intent-framework`의 `IntentPrediction`:
```python
status: Literal["accepted", "rejected"]
rejection_reason: Literal["ambiguous", "contradictory", "unknown_entity", "unsupported"]
```

**현재 IntentIR에 추가할 것:**
```python
class IntentPrediction(BaseModel):
    status: Literal["accepted", "rejected"]
    program: Optional[IntentIR] = None       # accepted일 때
    rejection_reason: Optional[str] = None   # rejected일 때
    # "ambiguous" | "contradictory" | "unknown_entity" | "unsupported"
```

**처리 예시:**
| 인텐트 | 거부 사유 |
|--------|----------|
| "optimize the network" | `ambiguous` — 구체적 동작 불명 |
| "allow h1→h2 and block h1→h2" | `contradictory` — 모순 |
| "block traffic from h9 to h10" | `unknown_entity` — 토폴로지에 없는 호스트 |
| "set up MPLS tunnel from h1 to h4" | `unsupported` — 미지원 기능 |

**Stage 1 파서 + Stage 5 XAI** 모두 수정 필요.

---

#### [신규] B-2. 토폴로지 그라운딩 — 🔴 높음

**현재 문제**: LLM이 없는 호스트(`h9`), 없는 스위치(`switch 99`)를 생성해도 탐지 불가. Stage 3 정적 검증에서도 이를 잡지 못함.

**참조**: `sdn_intent-framework`의 `topology.json`을 LLM 프롬프트에 주입:
```json
{
  "entities": [
    {"id": "host:h1", "aliases": ["h1", "10.0.0.1"]},
    {"id": "host:h2", "aliases": ["h2", "10.0.0.2"]}
  ],
  "devices": [
    {"id": "device:s1", "aliases": ["s1", "of:0000000000000001"]}
  ],
  "ports": {
    "of:0000000000000001": [1, 2, 3, 4]
  }
}
```

**구현 위치**: `stage1_intent/intent_parser.py` 프롬프트 구성 시 ONOS에서 실시간 토폴로지 조회 후 주입.

**장점**:
- 환각(hallucination) 억제
- `unknown_entity` 거부 사유 자동 판별 가능
- 논문 기여로 직접 쓸 수 있음 ("인가된 인벤토리 기반 환각 억제")

---

#### [신규] B-3. 정량적 평가 프레임워크 — 🔴 높음

**현재 문제**: 파이프라인이 얼마나 잘 동작하는지 측정하는 체계적 벤치마크 없음. 논문 5장 평가에서 수치 근거 부족.

**참조**: `sdn_intent-framework`의 평가 지표:

| 지표 | 의미 | 측정 방법 |
|------|------|----------|
| `normalized_exact_match` | IR 전체 일치율 | 예상 IR vs 실제 IR |
| `slot_accuracy` | 필드별 정확도 | src/dst/action/device 등 개별 비교 |
| `rejection_recall` | 거부해야 할 케이스 탐지율 | ambiguous 등 4종별 측정 |
| `hallucination_rate` | 없는 엔티티 생성 비율 | 토폴로지 인벤토리 대비 |

**구현 계획**:
1. `Intent2Flow-ONOS.csv` 기반 **테스트셋 50개** 구성 (train/test 분리)
2. `stage1_intent` 파싱 결과와 정답 IR 비교 스크립트 작성
3. LLM 직접 생성 (baseline) vs IR+컴파일러 방식 비교
4. 5회 반복 실행 → 평균 ± 표준편차 계산

**논문 Table 형식 (5.1절)**:
```
| 방법           | Exact Match | Slot Acc. | Halluc. Rate |
|----------------|-------------|-----------|--------------|
| LLM Direct     |    62.0%    |   71.3%   |    18.4%     |
| IR + Compiler  |    84.0%    |   91.2%   |     2.1%     |
| + Grounding    |    89.0%    |   94.5%   |     0.0%     |
```

---

#### [신규] B-4. Compound Intent (복합 인텐트) — 🟡 중간

**현재 문제**: 단일 인텐트에서 항상 1개 FlowRule만 생성. 현실의 인텐트는 복수 룰이 필요한 경우가 많음.

**예시**:
```
"allow web traffic from h1 to h2, but block SSH"
→ FlowRule 1: allow TCP/80 (h1 → h2)
→ FlowRule 2: block TCP/22 (h1 → h2)
```

**구현**:
- `IntentIR`에 `rules: list[SingleRule]` 추가 (현재는 단일 룰 필드 flat)
- 컴파일러가 `rules` 리스트를 순회하여 복수 flow 생성
- 정적 검증은 생성된 복수 flow 간 충돌도 체크

---

#### [신규] B-5. Repair 루프 — 🟡 중간

**현재 문제**: Stage 3 정적 검증 실패 → 즉시 REJECT. 자동 재시도 없음.

**참조**: `sdn_intent-framework` 설정:
```toml
repair = true
max_iterations = 3
```

**구현 흐름**:
```
Stage 1 → Stage 2 → Stage 3 실패
  ↓
오류 피드백 생성 ("Shadowing conflict with existing priority 40000 rule")
  ↓
Stage 1 재호출 (오류 포함 프롬프트)
  ↓
최대 3회 반복 → 성공하면 Stage 4로 진행
```

**논문 기여**: "자동 수정(Repair) 루프로 LLM 1회 호출 대비 파싱 성공률 X% 향상"

---

### 보완 항목 통합 우선순위

기존 우선순위에 신규 항목 포함:

| 순위 | 항목 | 난이도 | 논문 임팩트 |
|------|------|--------|------------|
| 🔴 1 | **B-2 토폴로지 그라운딩** | 낮음 | 환각 억제 — 프롬프트 수정만으로 즉시 효과 |
| 🔴 2 | **B-3 정량 평가 프레임워크** | 중 | 논문 5장 수치 근거 필수 |
| 🔴 3 | **B-1 Rejection 처리** | 중 | IR 설계 완성도 + 평가에 필요 |
| 🔴 4 | **Stage 4 iperf 대역폭 검증** | 중 | Digital Twin 정밀도 |
| 🔴 5 | **Stage 5 Rollback XAI 설명** | 중 | XAI 차별화 포인트 |
| 🟡 6 | **Stage 1 SFC + reroute** | 중 | 인텐트 유형 다양화 |
| 🟡 7 | **B-4 Compound Intent** | 중 | 지원 범위 확장 |
| 🟡 8 | **Stage 5 Confidence 점수** | 중 | 정량 평가 지원 |
| 🟡 9 | **B-5 Repair 루프** | 중 | 자동화 완성도 |
| 🟢 10 | Stage 4 Rollback 정책 선택 | 중 | 운영 현실성 |
| 🟢 11 | Stage 2 멀티-플로우 (reroute) | 높음 | 경로 최적화 |
| 🟢 12 | Stage 6 배포 후 모니터링 | 중 | 완성도 |
