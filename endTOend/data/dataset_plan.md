# 평가 데이터셋 설계 계획 (150케이스)

> 목적: 논문 Section 5.1(파싱 정확도), 5.2(충돌 탐지) 평가에 사용할 데이터셋 구축  
> 기존: `sdn_intent-framework/experiments/e1/data/intents.jsonl` (100케이스)  
> 목표: `endTOend/data/intents_v2.jsonl` (150케이스)

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

| 이름 | ONOS Device ID | 유효 포트 |
|------|---------------|----------|
| s1 | `of:0000000000000001` | 1, 2, 3, 4, 9 |
| s2 | `of:0000000000000002` | 1, 2, 4, 5, 6, 7, 8, 10 |
| s3 | `of:0000000000000003` | 1, 2, 3 |
| s4 | `of:0000000000000004` | 1, 2, 5 |

> **Q. 스위치/호스트는 ONOS에서 미리 가정되는가?**  
> 스위치: OpenFlow로 연결되면 ONOS가 자동 발견 (DPID → of:000...N 자동 부여)  
> 호스트: 첫 패킷(ARP 등) 발생 시 ONOS가 자동 학습 (MAC/IP/포트 매핑)  
> FlowRule의 `deviceId`는 연결된 스위치만 허용. `criteria`의 IP는 호스트가 없어도 설치 가능.  
> → 데이터셋은 s1~s4, 10.0.0.1~10.0.0.4 범위 안에서 설계한다.

---

## 2. 기존 데이터셋 분석 (100케이스)

| 카테고리 | 수 | 특징 |
|---------|-----|------|
| forwarding | 42 | OUTPUT port, 기본 TCP/UDP/ICMP |
| security | 23 | NOACTION (DROP), src/dst IP 기반 |
| qos | 23 | QUEUE instruction, OUTPUT port |
| compound | 2 | 다중 rule (현재 파이프라인 미지원) |
| rejection | 10 | 모호/모순/미지원 인텐트 |

**기존 데이터셋의 한계:**
- **in_port (ingress port) 매칭** 케이스가 소수 (N004, N012, N020 등 업스트림에만)
- **src_port (출발지 포트)** 매칭 케이스 없음
- **서비스 별칭** (SSH, HTTPS, RDP, FTP 등) 표현 적음
- **서브넷 단위 IP** (10.0.0.0/24) 케이스 없음
- **s2~s4 중심** 케이스 부족 (대부분 s1 또는 s4)
- **rejection 유형 다양성** 부족

---

## 3. 신규 데이터셋 설계 (150케이스)

### 3.1 전체 분포

| 카테고리 | 기존 활용 | 신규 추가 | 합계 | 비율 |
|---------|----------|----------|------|------|
| forwarding | 42 | +13 | 55 | 37% |
| security | 23 | +17 | 40 | 27% |
| qos | 23 | +7 | 30 | 20% |
| rejection | 10 | +5 | 15 | 10% |
| compound | 2 | +8 | 10 | 6% |
| **합계** | **100** | **+50** | **150** | 100% |

### 3.2 신규 케이스 유형 (50케이스 상세)

#### A. Ingress Port 매칭 (in_port) — 10케이스

기존 데이터셋에 소수만 있던 유형. 입력 포트 기반 라우팅은 실제 운영에서 자주 쓰임.

```
"Forward traffic arriving on port 2 of switch 1 to port 3."
"Block packets entering switch 4 on port 5."
"Route all traffic from port 1 of switch 2 to port 4."
```

| 필드 | 값 |
|------|-----|
| criteria | IN_PORT |
| 포함 카테고리 | forwarding 6, security 4 |

#### B. Source Port 매칭 (src_port) — 8케이스

기존 데이터셋에 전혀 없는 유형. 출발지 포트 기반 필터링.

```
"Block all traffic originating from source port 80 on switch 1."
"Forward UDP traffic from source port 53 to port 2 on switch 1."
"Deny traffic from source port 8080 destined for 10.0.0.4 on switch 4."
```

| 필드 | 값 |
|------|-----|
| criteria | TCP_SRC 또는 UDP_SRC |
| 포함 카테고리 | security 5, forwarding 3 |

#### C. 서비스 별칭 표현 — 12케이스

포트 번호 대신 서비스 이름으로 인텐트를 표현. LLM 파싱 난이도 상승.

| 서비스 | 포트/프로토콜 | 예시 인텐트 |
|--------|-------------|-----------|
| SSH | tcp/22 | "Block SSH from h1 to h4 on switch 1." |
| HTTPS | tcp/443 | "Allow HTTPS from h2 to h3 via port 2 on switch 1." |
| RDP | tcp/3389 | "Deny RDP access from h4 to h1 on switch 4." |
| FTP | tcp/21 | "Block FTP traffic from 10.0.0.1 to 10.0.0.4 on switch 4." |
| SMTP | tcp/25 | "Forward SMTP from h2 to h3 via port 2 on switch 1." |
| DNS | udp/53 | "Allow DNS queries from h3 to h2 on switch 3." |

포함 카테고리: security 7, forwarding 5

#### D. 서브넷 단위 IP — 8케이스

특정 호스트가 아닌 서브넷 전체에 대한 정책.

```
"Block all traffic from 10.0.0.0/24 on switch 1."
"Forward traffic destined for 10.0.0.0/24 to port 2 on switch 2."
"Deny all IPv4 traffic from subnet 10.0.0.0/24 to 10.0.0.4 on switch 4."
```

| 필드 | 값 |
|------|-----|
| criteria | IPV4_SRC 또는 IPV4_DST (CIDR) |
| 포함 카테고리 | security 5, forwarding 3 |

#### E. s2/s3/s4 중심 케이스 — 7케이스

기존 데이터셋이 s1 편중. s2~s4를 명시적으로 타겟.

```
"Forward HTTP traffic on switch 2 from port 4 to port 5."
"Block all traffic from h1 to h2 on switch 3."
"Route UDP DNS traffic to port 1 on switch 2."
```

#### F. Compound (다중 규칙) — 8케이스

하나의 인텐트에 여러 FlowRule이 필요한 경우.  
현재 파이프라인은 미지원이지만, rejection 또는 향후 확장을 위한 케이스로 포함.

```
"Allow HTTP from h1 to h3 but block all other traffic from h1 on switch 1."
"Forward TCP/80 to port 2 and forward UDP/53 to port 3 on switch 1."
```

#### G. Rejection 추가 유형 — 5케이스

기존 rejection 10케이스(모호/모순/미지원)에 추가.

| 유형 | 예시 |
|------|------|
| 미지원 스위치 | "Apply policy on switch 10." (토폴로지에 없음) |
| 미지원 프로토콜 | "Block GRE traffic on switch 1." |
| 모순 (동일 match, 다른 action) | "Forward and block all traffic from h1 to h4." |
| 미지원 action | "Throttle bandwidth from h1 to h3 on switch 1." |
| 불완전 인텐트 | "Block traffic on switch 1." (src/dst 미지정) |

---

## 4. 파일 형식

기존 `intents.jsonl`과 동일한 JSONL 포맷 사용.  
신규 케이스는 `cohort: "xai_extended"` 로 구분.

```jsonl
{
  "id": "E001",
  "cohort": "xai_extended",
  "category": "forwarding",
  "variation": "in_port",
  "instruction": "Forward traffic arriving on port 2 of switch 1 to port 3.",
  "expected": {
    "status": "accepted",
    "program": {
      "rules": [{
        "intent_type": "forwarding",
        "action": "forward",
        "selector": {
          "source": null,
          "destination": null,
          "eth_type": null,
          "protocol": null,
          "source_port": null,
          "destination_port": null,
          "ingress_port": 2
        },
        "qos": null,
        "enforcement": {
          "device": "of:0000000000000001",
          "egress_port": "3",
          "set_vlan_id": null
        }
      }]
    },
    "rejection": null
  }
}
```

rejection 케이스:
```jsonl
{
  "id": "E140",
  "cohort": "xai_extended",
  "category": "rejection",
  "variation": "unknown_device",
  "instruction": "Apply firewall policy on switch 10.",
  "expected": {
    "status": "rejected",
    "program": null,
    "rejection": {
      "reason": "unknown_entity",
      "detail": "switch 10 does not exist in topology"
    }
  }
}
```

---

## 5. 생성 방법

### Step 1: 기존 100케이스 그대로 복사 (100개)

`sdn_intent-framework/experiments/e1/data/intents.jsonl` → `endTOend/data/intents_v2.jsonl`  
cohort 값은 원본 그대로 유지.

### Step 2: 신규 50케이스 수작업 작성

`endTOend/data/generate_dataset.py` 스크립트로 템플릿 기반 생성 후 수동 검토.

신규 케이스 ID 체계:
- `E001` ~ `E050`: 신규 50케이스 (xai_extended cohort)

### Step 3: 검증

```bash
cd endTOend/
python data/validate_dataset.py data/intents_v2.jsonl
```

검증 항목:
- JSON 파싱 가능 여부
- 필수 필드 존재 여부 (id, instruction, expected)
- deviceId가 토폴로지 내 유효한지
- 포트 번호가 해당 스위치 유효 포트인지
- accepted 케이스에 program 존재, rejected 케이스에 rejection 존재

---

## 6. 최종 구성 목표

```
endTOend/data/
  intents_v2.jsonl       # 150케이스 전체 (기존 100 + 신규 50)
  dataset_plan.md        # 이 파일
  generate_dataset.py    # 신규 50케이스 생성 스크립트
  validate_dataset.py    # 데이터셋 검증 스크립트
```

---

## 7. 논문 활용 계획

| 데이터셋 활용 | 실험 | 케이스 수 |
|-------------|------|----------|
| accepted 전체 | 5.1 파싱 정확도 (slot_accuracy) | 135케이스 |
| accepted 전체 | 5.1 컴파일 성공률 | 135케이스 |
| accepted 전체 | 5.1 hallucination_rate | 135케이스 |
| rejection 케이스 | 5.1 거부 탐지율 | 15케이스 |
| 충돌 포함 쌍 | 5.2 conflict precision/recall | sec5_2/run.py 별도 케이스 |
