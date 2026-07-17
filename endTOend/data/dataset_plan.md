# 평가 데이터셋 설계 계획 (150케이스)

> 목적: 논문 Section 5.1(파싱 정확도), 5.2(충돌 탐지) 평가에 사용할 데이터셋 구축  
> 기존: `sdn_intent-framework/experiments/e1/data/intents.jsonl` (100케이스)  
> 목표: `endTOend/data/intents_v2.jsonl` (150케이스 = 기존 100 + 신규 50)  
> 신규 유형: **SFC (Service Function Chaining) 25케이스 + Reroute 25케이스**

---

## 1. 토폴로지 전제 (고정)

FlowRule은 아래 토폴로지를 **가정**하고 생성된다.  
실제 ONOS에 배포할 때는 이 스위치들이 OpenFlow로 연결되어 있어야 한다.

```
h1 (10.0.0.1) ──┐
h2 (10.0.0.2) ──┤── s1 ──── s2
h3 (10.0.0.3) ──┤     \    /
h4 (10.0.0.4) ──┘      s3─s4
```

| 이름 | ONOS Device ID | 유효 포트 | 역할 (실험용 가정) |
|------|---------------|----------|-----------------|
| s1 | `of:0000000000000001` | 1, 2, 3, 4, 9 | 진입 스위치. port 9 = 방화벽 연결 |
| s2 | `of:0000000000000002` | 1, 2, 4, 5, 6, 7, 8, 10 | IDS/LB 서비스 노드 |
| s3 | `of:0000000000000003` | 1, 2, 3 | 대안 경로 스위치 |
| s4 | `of:0000000000000004` | 1, 2, 5 | 출구 스위치 |

> **Q. 스위치/호스트는 ONOS에서 미리 가정되는가?**  
> 스위치: OpenFlow로 연결되면 ONOS가 자동 발견 (DPID → of:000...N 자동 부여)  
> 호스트: 첫 패킷(ARP 등) 발생 시 ONOS가 자동 학습 (MAC/IP/포트 매핑)  
> FlowRule의 `deviceId`는 연결된 스위치만 허용. `criteria`의 IP는 호스트가 없어도 설치 가능.  
> → 데이터셋은 s1~s4, 10.0.0.1~10.0.0.4 범위 안에서 설계한다.

---

## 2. 기존 데이터셋 분석 (100케이스)

| 카테고리 | 수 | FlowRule 특징 |
|---------|-----|--------------|
| forwarding | 42 | OUTPUT port, 기본 TCP/UDP/ICMP |
| security | 23 | NOACTION (DROP), src/dst IP 기반 |
| qos | 23 | QUEUE instruction + OUTPUT port |
| compound | 2 | 다중 rule (현재 파이프라인 미지원) |
| rejection | 10 | 모호/모순/미지원 인텐트 |

**기존 데이터셋의 한계:**
- 단일 스위치 · 단일 홉 forwarding/security만 있음
- **서비스 체이닝(SFC)** — 중간 네트워크 기능을 거쳐 전달하는 케이스 없음
- **경로 재지정(Reroute)** — 대안 경로 또는 장애 우회 케이스 없음
- 복잡한 다중 스위치 시나리오 없음

---

## 3. 신규 유형 개념 정의

### SFC (Service Function Chaining)

트래픽이 목적지에 도달하기 전에 **하나 이상의 네트워크 기능(방화벽, IDS, LB 등)을 경유**하도록 강제하는 정책.

```
h1 → [s1] → port9(방화벽) → [s1] → [s2] → h3
             ↑ 검사 후 통과
```

ONOS FlowRule 표현 방식:
- **단일 스위치 우회**: s1에 두 개 룰 (진입 시 port9으로, 방화벽 복귀 후 목적지로)
- **다중 스위치 체인**: 각 홉마다 해당 스위치에 룰 설치

IntentIR 확장 필드:
```python
action: "sfc"
waypoints: ["s1:9", "s2"]   # 경유 지점 목록 (device:port 또는 device)
```

생성되는 FlowRule 예시 (s1에서 h1→h3 HTTP를 방화벽 경유):
```json
[
  {
    "deviceId": "of:0000000000000001",
    "priority": 45000,
    "selector": { "criteria": [
      {"type": "ETH_TYPE", "ethType": "0x800"},
      {"type": "IPV4_SRC", "ip": "10.0.0.1/32"},
      {"type": "IPV4_DST", "ip": "10.0.0.3/32"},
      {"type": "IP_PROTO", "protocol": 6},
      {"type": "TCP_DST", "tcpPort": 80}
    ]},
    "treatment": {"instructions": [{"type": "OUTPUT", "port": "9"}]}
  },
  {
    "deviceId": "of:0000000000000001",
    "priority": 44000,
    "selector": { "criteria": [
      {"type": "IN_PORT", "port": 9},
      {"type": "IPV4_DST", "ip": "10.0.0.3/32"}
    ]},
    "treatment": {"instructions": [{"type": "OUTPUT", "port": "2"}]}
  }
]
```

---

### Reroute (경로 재지정)

기존 경로 대신 **대안 경로로 트래픽을 우회**시키는 정책.  
링크 장애, 유지보수, 부하 분산이 주요 동기.

```
기존 경로: h1 → s1 → s3 → s4 → h4
재지정:    h1 → s1 → s2 → s4 → h4   (s3 장애 또는 우회)
```

ONOS FlowRule 표현 방식:
- 출력 포트(OUTPUT port)를 대안 경로 방향으로 변경
- 기존 경로 룰보다 높은 priority로 덮어씀

IntentIR 확장 필드:
```python
action: "reroute"
via_device: "s2"        # 경유할 대안 스위치
avoid_device: "s3"      # 회피할 스위치 (선택)
out_port: 4             # 대안 출력 포트
```

생성되는 FlowRule 예시 (s1에서 h4 방향 트래픽을 s2 경유로):
```json
{
  "deviceId": "of:0000000000000001",
  "priority": 40000,
  "selector": { "criteria": [
    {"type": "ETH_TYPE", "ethType": "0x800"},
    {"type": "IPV4_DST", "ip": "10.0.0.4/32"}
  ]},
  "treatment": {"instructions": [{"type": "OUTPUT", "port": "4"}]}
}
```

---

## 4. 신규 50케이스 상세 설계

### 4.1 SFC 케이스 (25케이스)

#### SFC-A. 단일 스위치 서비스 우회 (10케이스)

s1의 port 9에 연결된 **방화벽**을 경유하는 시나리오.  
실험상 가정: s1 port 9 = 외부 방화벽 장치 연결 포트.

| ID | 인텐트 예시 | src | dst | 프로토콜 | 경유 |
|----|-----------|-----|-----|---------|------|
| SFC-A01 | "Route HTTP from h1 to h3 through the firewall on switch 1 port 9." | h1 | h3 | tcp/80 | s1:9 |
| SFC-A02 | "Send all traffic from h2 to h4 via the firewall on switch 1." | h2 | h4 | any | s1:9 |
| SFC-A03 | "Forward SSH traffic from h1 to h3 through port 9 of switch 1 for inspection." | h1 | h3 | tcp/22 | s1:9 |
| SFC-A04 | "Inspect ICMP from h3 to h1 using the security function at switch 1 port 9." | h3 | h1 | icmp | s1:9 |
| SFC-A05 | "Route DNS traffic from h4 to h2 through the middlebox on port 9 of switch 1." | h4 | h2 | udp/53 | s1:9 |
| SFC-A06 | "All HTTPS traffic from h1 to h4 must pass through the firewall at switch 1 port 9." | h1 | h4 | tcp/443 | s1:9 |
| SFC-A07 | "Redirect FTP from h2 to h3 through the inspection device on switch 1 port 9." | h2 | h3 | tcp/21 | s1:9 |
| SFC-A08 | "Enforce traffic from 10.0.0.1 to 10.0.0.3 to pass through port 9 of switch 1." | 10.0.0.1 | 10.0.0.3 | any | s1:9 |
| SFC-A09 | "Send UDP traffic from h1 to h2 via security function at switch 1 port 9." | h1 | h2 | udp | s1:9 |
| SFC-A10 | "Force all traffic from h4 to h1 through the firewall at port 9 of switch 1." | h4 | h1 | any | s1:9 |

#### SFC-B. 다중 스위치 서비스 체인 (10케이스)

s2를 IDS/LB 서비스 노드로 가정하여 s1 → s2 → s4 체인.

| ID | 인텐트 예시 | 체인 경로 |
|----|-----------|---------|
| SFC-B01 | "Route HTTP from h1 to h4 through switch 2 for deep packet inspection." | s1→s2→s4 |
| SFC-B02 | "Forward all traffic from h2 to h4 via switch 2 as the IDS node." | s1→s2→s4 |
| SFC-B03 | "Send TCP port 443 traffic from h1 to h3 through switch 2 for load balancing." | s1→s2→s3 |
| SFC-B04 | "Route ICMP from h1 to h4 through switch 3 for monitoring." | s1→s3→s4 |
| SFC-B05 | "Chain all traffic from h2 to h3 through switch 2 then switch 4." | s1→s2→s4→s3 |
| SFC-B06 | "Apply IDS on switch 2 for HTTP traffic from h1 to h4, then deliver." | s1→s2→s4 |
| SFC-B07 | "Forward DNS from h3 to h1 via switch 3 for logging." | s4→s3→s1 |
| SFC-B08 | "Route all UDP from h4 to h2 through switch 3." | s4→s3→s1 |
| SFC-B09 | "Send FTP from h1 to h4 through switch 2 and switch 4." | s1→s2→s4 |
| SFC-B10 | "Apply firewall on switch 1 then IDS on switch 2 for h1 to h4 traffic." | s1→s2→s4 |

#### SFC-C. SFC + Security 결합 (5케이스)

방화벽 경유 후 DROP 또는 조건부 전달.

| ID | 인텐트 예시 |
|----|-----------|
| SFC-C01 | "Inspect traffic from h1 to h4 through port 9 of switch 1; drop if malicious." |
| SFC-C02 | "Route SMTP from h2 to h3 through the firewall; block if it fails inspection." |
| SFC-C03 | "Chain HTTP traffic from h1 through switch 2 IDS; forward clean traffic to h4." |
| SFC-C04 | "Apply security inspection on switch 1 port 9 for all traffic from h3 to h4." |
| SFC-C05 | "Send SSH from h1 through firewall at switch 1 port 9 before allowing to h4." |

---

### 4.2 Reroute 케이스 (25케이스)

#### Reroute-A. 대안 스위치 경유 (10케이스)

특정 스위치 장애 또는 혼잡 시 대안 경로로 우회.

| ID | 인텐트 예시 | 기존 경로 | 대안 경로 |
|----|-----------|---------|---------|
| RR-A01 | "Reroute traffic from h1 to h4 via switch 2 instead of switch 3." | s1→s3→s4 | s1→s2→s4 |
| RR-A02 | "Redirect all traffic from h2 to h4 through switch 3 if switch 2 is down." | s1→s2→s4 | s1→s3→s4 |
| RR-A03 | "Send h1 to h3 traffic via switch 3 to avoid switch 2 congestion." | s1→s2→s3 | s1→s3 |
| RR-A04 | "Reroute h3 to h1 packets through switch 2 to bypass switch 3." | s4→s3→s1 | s4→s2→s1 |
| RR-A05 | "Redirect HTTP traffic from h1 to h4 via switch 2 for maintenance on switch 3." | s1→s3→s4 | s1→s2→s4 |
| RR-A06 | "Reroute ICMP from h2 to h4 via switch 3 instead of switch 2." | s1→s2→s4 | s1→s3→s4 |
| RR-A07 | "Redirect all traffic from h1 to h4 to use switch 2 path starting now." | s1→s3→s4 | s1→s2→s4 |
| RR-A08 | "Bypass switch 3: reroute h4 to h1 via switch 2." | s4→s3→s1 | s4→s2→s1 |
| RR-A09 | "Reroute DNS from h4 to h2 through switch 2 instead of switch 3." | s4→s3→s1 | s4→s2→s1 |
| RR-A10 | "Force h2 to h3 traffic to take the switch 3 path, not switch 2." | s1→s2→s4 | s1→s3→s4 |

#### Reroute-B. 특정 포트로 경로 변경 (8케이스)

출력 포트를 명시적으로 지정하여 경로 변경.

| ID | 인텐트 예시 | 변경 포트 |
|----|-----------|---------|
| RR-B01 | "On switch 1, redirect traffic to h4 from port 3 to port 4." | port 3 → 4 |
| RR-B02 | "Change output port for h1 to h3 traffic on switch 1 from port 2 to port 3." | port 2 → 3 |
| RR-B03 | "Reroute traffic entering port 1 of switch 2 to exit on port 5 instead of port 4." | port 4 → 5 |
| RR-B04 | "Redirect h2 to h4 traffic on switch 1 to use port 4 instead of port 2." | port 2 → 4 |
| RR-B05 | "On switch 3, change egress port for h3 to h1 traffic from port 1 to port 2." | port 1 → 2 |
| RR-B06 | "Switch 1: redirect HTTP from h1 to h3 to go out on port 3 not port 2." | port 2 → 3 |
| RR-B07 | "Reroute UDP DNS on switch 1 to exit port 4 instead of port 1." | port 1 → 4 |
| RR-B08 | "On switch 2, redirect traffic for 10.0.0.4 to port 8 instead of port 4." | port 4 → 8 |

#### Reroute-C. 장애 우회 (Failover) 시나리오 (7케이스)

링크 또는 노드 장애를 가정한 긴급 경로 변경.

| ID | 인텐트 예시 | 장애 요소 |
|----|-----------|---------|
| RR-C01 | "If switch 3 fails, redirect all h1 to h4 traffic through switch 2." | s3 down |
| RR-C02 | "Failover: send h2 to h4 via switch 2 when switch 3 link is unavailable." | s1-s3 link |
| RR-C03 | "Emergency reroute: bypass switch 2 and send h1 to h3 traffic via switch 3." | s2 down |
| RR-C04 | "Reroute all traffic on switch 3 port 2 to switch 2 port 4 during maintenance." | s3:port2 |
| RR-C05 | "Redirect h3 to h1 traffic from switch 4 via switch 2 if switch 3 is unreachable." | s3 unreachable |
| RR-C06 | "Primary path down: reroute h1 to h4 traffic through s2 immediately." | primary path |
| RR-C07 | "Backup path activation: send all TCP traffic from h2 to h4 via switch 3." | backup |

---

## 5. IntentIR 확장 설계

신규 유형을 지원하려면 `models/intent_ir.py`와 `stage2_flowrule/compiler.py`를 확장해야 한다.

### 5.1 IntentIR 신규 필드

```python
@dataclass
class IntentIR:
    # 기존 필드
    action: Literal["block", "forward", "qos", "sfc", "reroute"]  # 확장
    ...

    # SFC 전용
    waypoints: list[str] | None = None   # ["s1:9", "s2"] — 경유 지점
    
    # Reroute 전용
    via_device: str | None = None        # "s2" — 경유 스위치
    avoid_device: str | None = None      # "s3" — 회피 스위치
    alt_out_port: int | None = None      # 대안 출력 포트
```

### 5.2 컴파일러 동작

| action | 생성되는 FlowRule 수 | 핵심 instruction |
|--------|-------------------|----------------|
| `sfc` | 2개 이상 (경유지당 1~2개) | OUTPUT to waypoint port |
| `reroute` | 1개 (기존 경로 override) | OUTPUT to alt_out_port |

### 5.3 데이터셋에서의 표현 방식

SFC · Reroute는 규칙이 여러 개이므로 `rules` 배열에 복수 항목으로 표현:

```json
{
  "id": "SFC-A01",
  "category": "sfc",
  "variation": "single_switch_bypass",
  "instruction": "Route HTTP from h1 to h3 through the firewall on switch 1 port 9.",
  "expected": {
    "status": "accepted",
    "program": {
      "rules": [
        {
          "intent_type": "sfc",
          "action": "forward",
          "selector": { "source": {"ip": "10.0.0.1"}, "destination": {"ip": "10.0.0.3"},
                        "eth_type": "ipv4", "protocol": "tcp", "destination_port": 80 },
          "enforcement": { "device": "of:0000000000000001", "egress_port": "9" },
          "sfc_role": "ingress"
        },
        {
          "intent_type": "sfc",
          "action": "forward",
          "selector": { "ingress_port": 9, "destination": {"ip": "10.0.0.3"} },
          "enforcement": { "device": "of:0000000000000001", "egress_port": "2" },
          "sfc_role": "egress"
        }
      ],
      "sfc_chain": ["of:0000000000000001:9"]
    }
  }
}
```

---

## 6. 파일 구성 목표

```
endTOend/data/
  dataset_plan.md        # 이 파일
  intents_v2.jsonl       # 150케이스 (기존 100 + SFC 25 + Reroute 25)
  generate_dataset.py    # 신규 50케이스 생성 스크립트
  validate_dataset.py    # 데이터셋 검증 스크립트
```

---

## 7. 생성 방법

### Step 1: 기존 100케이스 복사

```bash
cp sdn_intent-framework/experiments/e1/data/intents.jsonl endTOend/data/intents_v2.jsonl
```

### Step 2: 신규 50케이스 생성

```bash
cd endTOend/
python data/generate_dataset.py    # SFC 25 + Reroute 25 케이스 생성 후 intents_v2.jsonl에 추가
```

### Step 3: 검증

```bash
python data/validate_dataset.py data/intents_v2.jsonl
# 출력: 총 150케이스, 카테고리별 수, 오류 목록
```

---

## 8. 논문 활용

| 데이터 | 실험 섹션 | 케이스 수 |
|--------|---------|---------|
| 기존 100 (accepted) | 5.1 파싱 정확도 baseline | 90케이스 |
| 신규 SFC 25 | 5.1 SFC 파싱 정확도 | 25케이스 |
| 신규 Reroute 25 | 5.1 Reroute 파싱 정확도 | 25케이스 |
| 전체 150 | 5.1 종합 slot_accuracy | 140케이스 (rejection 제외) |
| SFC/Reroute | 5.3 Digital Twin 검증 | 선택 6케이스 |
