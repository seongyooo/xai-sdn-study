# 데이터셋 및 컴파일러 설계 문서

> 대상 파일: `endTOend/data/intents_v2.jsonl`, `endTOend/stage2_flowrule/compiler.py`

---

## 1. 데이터셋 개요 (`intents_v2.jsonl`)

### 1.1 구성

| cohort | 출처 | 케이스 수 |
|--------|------|---------|
| `project_authored` | 직접 작성 (sdn-intent-framework) | 50 |
| `project` | 이번 연구에서 신규 작성 (SFC + Reroute) | 50 |
| **합계** | | **100** |

> `upstream` cohort(NetIntent GitHub 레포 원본 50케이스)는 라이선스 문제로 제외.  
> 참조 위치: `sdn_intent-framework/experiments/e1/data/intents.jsonl`

### 1.2 카테고리 분포

| category | 케이스 수 | status | 설명 |
|----------|---------|--------|------|
| `forwarding` | 15 | accepted | 단일 스위치 포트 기반 전달 |
| `security` | 15 | accepted | DROP/NOACTION 블로킹 |
| `qos` | 10 | accepted | QUEUE + OUTPUT 조합 |
| `ambiguous_unsupported` | 10 | rejected | 모호/불가능 인텐트 |
| `sfc` | 25 | accepted | 서비스 체이닝 (신규) |
| `reroute` | 25 | accepted | 경로 재지정 (신규) |

### 1.3 JSONL 레코드 형식

```json
{
  "id": "SFC-A01",
  "cohort": "project",
  "category": "sfc",
  "variation": "single_switch_bypass",
  "instruction": "Route HTTP from 10.0.0.1 to 10.0.0.3 through the firewall on switch 1 port 9.",
  "expected": {
    "status": "accepted",
    "program": {
      "rules": [
        {
          "intent_type": "sfc",
          "action": "forward",
          "selector": {
            "source": {"host": null, "ip": "10.0.0.1"},
            "destination": {"host": null, "ip": "10.0.0.3"},
            "eth_type": "ipv4",
            "protocol": "tcp",
            "destination_port": 80,
            "source_port": null,
            "ingress_port": null
          },
          "qos": null,
          "enforcement": {"device": "of:0000000000000001", "egress_port": "9", "set_vlan_id": null},
          "sfc_role": "ingress"
        },
        {
          "intent_type": "sfc",
          "action": "forward",
          "selector": {
            "source": null,
            "destination": {"host": null, "ip": "10.0.0.3"},
            "eth_type": "ipv4",
            "protocol": null,
            "destination_port": null,
            "source_port": null,
            "ingress_port": 9
          },
          "qos": null,
          "enforcement": {"device": "of:0000000000000001", "egress_port": "1", "set_vlan_id": null},
          "sfc_role": "egress"
        }
      ],
      "sfc_chain": ["of:0000000000000001:9"]
    },
    "rejection": null
  }
}
```

**기존 필드와의 차이점:**
- SFC: `rules` 배열에 2개 이상의 룰, `sfc_role` 필드(`ingress`/`transit`/`egress`), `sfc_chain` 리스트
- Reroute: `intent_type: "reroute"`, 단일 룰 (기존 forwarding과 동일 구조, action="forward")
- 평가 기준: `rules[0]` (ingress/primary rule)만 사용

---

## 2. 토폴로지 전제

모든 신규 케이스는 아래 diamond 토폴로지를 가정한다.

```
h1 (10.0.0.1) ─── s1:port3
h2 (10.0.0.2) ─── s1:port4
                   s1:port1 ─── s2:port1 ─── s4:port1
                   s1:port2 ─── s3:port1 ─── s4:port2
                   s1:port9 ─── [firewall]
                                             s4:port3 ─── h3 (10.0.0.3)
                                             s4:port4 ─── h4 (10.0.0.4)
```

| 스위치 | ONOS Device ID | 주요 포트 역할 |
|--------|---------------|-------------|
| s1 | `of:0000000000000001` | port1→s2(slow,1Mbps), port2→s3(fast,10Mbps), port3→h1, port4→h2, port9→방화벽 |
| s2 | `of:0000000000000002` | port1→s1, port2→s4 |
| s3 | `of:0000000000000003` | port1→s1, port2→s4 |
| s4 | `of:0000000000000004` | port1→s2, port2→s3, port3→h3, port4→h4 |

---

## 3. 신규 케이스 설계

### 3.1 SFC (Service Function Chaining) — 25케이스

트래픽이 목적지에 도달하기 전에 **중간 네트워크 기능(방화벽·IDS·LB 등)을 경유**하도록 강제하는 정책.

#### SFC-A: 단일 스위치 서비스 우회 (10케이스)

s1:port9에 연결된 방화벽을 경유하는 시나리오.

| ID | 인텐트 | src | dst | 프로토콜 | waypoint | egress |
|----|--------|-----|-----|---------|---------|-------|
| SFC-A01 | HTTP h1→h3 via firewall | 10.0.0.1 | 10.0.0.3 | tcp/80 | s1:port9 | s1:port1 |
| SFC-A02 | All traffic h2→h4 via firewall | 10.0.0.2 | 10.0.0.4 | — | s1:port9 | s1:port1 |
| SFC-A03 | SSH h1→h3 via port 9 | 10.0.0.1 | 10.0.0.3 | tcp/22 | s1:port9 | s1:port1 |
| SFC-A04 | ICMP h3→h1 via firewall | 10.0.0.3 | 10.0.0.1 | icmp | s1:port9 | s1:port3 |
| SFC-A05 | DNS h4→h2 via middlebox | 10.0.0.4 | 10.0.0.2 | udp/53 | s1:port9 | s1:port4 |
| SFC-A06 | HTTPS h1→h4 via firewall | 10.0.0.1 | 10.0.0.4 | tcp/443 | s1:port9 | s1:port1 |
| SFC-A07 | FTP h2→h3 via inspection | 10.0.0.2 | 10.0.0.3 | tcp/21 | s1:port9 | s1:port1 |
| SFC-A08 | Any h1→h3 via port 9 | 10.0.0.1 | 10.0.0.3 | — | s1:port9 | s1:port1 |
| SFC-A09 | UDP h1→h2 via security fn | 10.0.0.1 | 10.0.0.2 | udp | s1:port9 | s1:port4 |
| SFC-A10 | Any h4→h1 via firewall | 10.0.0.4 | 10.0.0.1 | — | s1:port9 | s1:port3 |

#### SFC-B: 다중 스위치 서비스 체인 (10케이스)

s2를 IDS/LB 서비스 노드로 가정한 s1→s2→s4 체인.

| ID | 체인 경로 | 설명 |
|----|----------|------|
| SFC-B01 | s1→s2→s4 | HTTP h1→h4, s2에서 DPI |
| SFC-B02 | s1→s2→s4 | All h2→h4, s2가 IDS 역할 |
| SFC-B03 | s1→s2→s4 | TCP/443 h1→h3, s2에서 LB |
| SFC-B04 | s1→s3→s4 | ICMP h1→h4, s3에서 모니터링 |
| SFC-B05 | s1→s2→s4 | h2→h3, s2·s4 경유 체인 |
| SFC-B06 | s1→s2→s4 | HTTP h1→h4, s2 IDS 후 전달 |
| SFC-B07 | s4→s3→s1 | DNS h3→h1, s3에서 로깅 |
| SFC-B08 | s4→s3→s1 | UDP h4→h2, s3 경유 |
| SFC-B09 | s1→s2→s4 | FTP h1→h4, s2·s4 경유 |
| SFC-B10 | s1→s1:9→s2→s4 | h1→h4, 방화벽+IDS 이중 체인 |

#### SFC-C: SFC + Security 결합 (5케이스)

방화벽 경유 후 조건부 DROP (검사 실패 시 차단) 시나리오.

| ID | 인텐트 | waypoint |
|----|--------|---------|
| SFC-C01 | Inspect h1→h4 via port9; drop if malicious | s1:port9 |
| SFC-C02 | SMTP h2→h3 via firewall; block if fails | s1:port9 |
| SFC-C03 | HTTP h1→h4 via s2 IDS; forward clean | s2 |
| SFC-C04 | All h1→h4 via security inspection at s1:9 | s1:port9 |
| SFC-C05 | SSH h1→h4 via firewall at s1:9 | s1:port9 |

---

### 3.2 Reroute (경로 재지정) — 25케이스

기존 경로 대신 **대안 경로로 트래픽을 우회**시키는 정책.

#### Reroute-A: 대안 스위치 경유 (10케이스)

| ID | 원래 경로 | 대안 경로 | 주요 규칙 |
|----|----------|----------|---------|
| RR-A01 | s1→s3→s4 | s1→s2→s4 | s1: dst=10.0.0.4 → port1 |
| RR-A02 | s1→s2→s4 | s1→s3→s4 | s1: dst=10.0.0.4 → port2 |
| RR-A03 | s1→s2→s4 | s1→s3 직접 | s1: dst=10.0.0.3 → port2 |
| RR-A04 | s4→s3→s1 | s4→s2→s1 | s4: dst=10.0.0.1 → port1 |
| RR-A05 | s1→s3→s4 | s1→s2→s4 | s1: tcp/80, dst=10.0.0.4 → port1 |
| RR-A06 | s1→s2→s4 | s1→s3→s4 | s1: icmp, dst=10.0.0.4 → port2 |
| RR-A07 | s1→s3→s4 | s1→s2→s4 | s1: dst=10.0.0.4 → port1 |
| RR-A08 | s4→s3→s1 | s4→s2→s1 | s4: dst=10.0.0.1 → port1 |
| RR-A09 | s4→s3→s1 | s4→s2→s1 | s4: udp/53, dst=10.0.0.2 → port1 |
| RR-A10 | s1→s2→s4 | s1→s3→s4 | s1: dst=10.0.0.3 → port2 |

#### Reroute-B: 명시적 포트 변경 (8케이스)

| ID | 대상 스위치 | 변경 내용 |
|----|-----------|---------|
| RR-B01 | s1 | dst=10.0.0.4: port2 → port1 |
| RR-B02 | s1 | HTTP h1→h3: → port2 |
| RR-B03 | s2 | in_port=1 → port2 |
| RR-B04 | s1 | h2→h4: port1 → port2 |
| RR-B05 | s4 | h3→h1: port1 → port2 |
| RR-B06 | s1 | HTTP h1→h3: → port1 |
| RR-B07 | s1 | UDP DNS: → port2 |
| RR-B08 | s4 | dst=10.0.0.1: port1 → port2 |

#### Reroute-C: 장애 우회 (Failover) (7케이스)

| ID | 장애 요소 | 우회 경로 |
|----|---------|---------|
| RR-C01 | s3 down | h1→h4: s1→s2 (port1) |
| RR-C02 | s1-s3 링크 | h2→h4: s1→s2 (port1) |
| RR-C03 | s2 down | h1→h3: s1→s3 (port2) |
| RR-C04 | s4:port1 유지보수 | s4 in_port=1 → port2 |
| RR-C05 | s3 unreachable | h3→h1: s4→s2 (port1) |
| RR-C06 | primary path down | h1→h4: s1→s2 (port1) |
| RR-C07 | backup 활성화 | TCP h2→h4: s1→s3 (port2) |

---

## 4. IntentIR 확장

`models/intent_ir.py`에 추가된 필드:

| 필드 | 타입 | 용도 |
|------|------|------|
| `action` | `"sfc" \| "reroute"` (확장) | 인텐트 유형 |
| `alt_out_port` | `int \| None` | SFC: waypoint 이후 출력 포트 / Reroute: 새 출력 포트 |
| `waypoints` | `list[str] \| None` | SFC: `["switch 1:9", "switch 2"]` 형식 경유 지점 |
| `via_device` | `str \| None` | Reroute: 경유할 스위치 힌트 |
| `avoid_device` | `str \| None` | Reroute: 회피할 스위치 힌트 |

`from_llm_output()` 의미적 매핑:

| LLM 출력 키워드 | 변환 action |
|--------------|------------|
| "chain", "sfc", "waypoint", "inspect", "middlebox" | `"sfc"` |
| "reroute", "redirect", "failover", "bypass" | `"reroute"` |

---

## 5. 컴파일러 (`stage2_flowrule/compiler.py`)

### 5.1 action별 FlowRule 생성 방식

| action | flows 수 | 핵심 로직 |
|--------|---------|---------|
| `block` | 1 | `NOACTION` instruction |
| `forward` | 1 | `OUTPUT(out_port)` 또는 `OUTPUT(NORMAL)` |
| `qos` | 1 | `OUTPUT(out_port)` + `QUEUE(queue_id)` |
| `reroute` | 1 | `OUTPUT(alt_out_port ?? out_port ?? NORMAL)` |
| `sfc` | 2 | ingress(→waypoint) + egress(waypoint→alt_out_port) |

### 5.2 SFC 컴파일 상세

```
ingress FlowRule:
  priority = 45000 (DEFAULT_PRIORITY["sfc"])
  criteria = [ETH_TYPE, IPV4_SRC, IPV4_DST, IP_PROTO, TCP/UDP_DST, ...]
  treatment = OUTPUT(waypoint_port)

egress FlowRule:
  priority = 44000 (ingress - 1000)
  criteria = [ETH_TYPE, IN_PORT(waypoint_port), IPV4_DST]
  treatment = OUTPUT(alt_out_port)  ← 없으면 NORMAL
```

waypoint 포트 결정 우선순위:
1. `waypoints[0]`에서 파싱 (`"switch 1:9"` → `"9"`)
2. `ir.out_port` fallback
3. 둘 다 없으면 `CompileError`

egress rule의 criteria는 최소화 (ETH_TYPE, IN_PORT, IPV4_DST만 사용):
- 방화벽/IDS를 통과한 트래픽은 이미 검사 완료 → 프로토콜 재매칭 불필요

### 5.3 Reroute 컴파일

```python
out_port = ir.alt_out_port or ir.out_port  # alt_out_port 우선
treatment = OUTPUT(out_port or "NORMAL")
# 나머지는 forward와 동일
```

### 5.4 우선순위 기본값

| action | DEFAULT_PRIORITY |
|--------|----------------|
| `block` | 50000 |
| `sfc` | 45000 |
| `qos` | 40000 |
| `reroute` | 40000 |
| `forward` | 32768 |

---

## 6. 평가 (`evaluate.py`)

### 6.1 변경 사항

- **기본 데이터셋**: `intents_v2.jsonl` (project + project_authored 100케이스)
- **compound 스킵 기준**: `rules > 1` → `category == "compound"` (SFC의 다중 룰은 스킵 안 함)
- **SFC/Reroute action 매핑**: `intent_type == "sfc"` → `action = "sfc"` 등
- **`--category` 옵션**: `forwarding / security / qos / sfc / reroute / all`

### 6.2 SFC 평가 방식

SFC는 `rules[0]` (ingress rule)만 평가 기준으로 사용한다.

평가 슬롯:

| 슬롯 | gold 출처 | 비고 |
|------|----------|------|
| `action` | `"sfc"` | LLM이 "sfc"로 분류해야 함 |
| `device_num` | `enforcement.device` (→ 정수 N) | ingress rule의 장치 |
| `src_ip` | `selector.source.ip` | |
| `dst_ip` | `selector.destination.ip` | |
| `ip_proto` | `selector.protocol` | |
| `dst_port` | `selector.destination_port` | |

`out_port`(waypoint 포트)는 현재 SLOT_FIELDS에 미포함 (별도 분석 가능).

### 6.3 평가 실행 예시

```bash
cd endTOend/

# 전체 평가
python evaluate.py --model qwen3:8b

# SFC만 빠르게 테스트
python evaluate.py --category sfc --limit 5

# Reroute 카테고리
python evaluate.py --category reroute

# LLM 없이 컴파일러만 (구조 검증용)
python evaluate.py --skip-llm
```

---

## 7. 파일 구성

```
endTOend/data/
  intents_v2.jsonl       ← 100케이스 (project_authored 50 + project 50)
  generate_dataset.py    ← 신규 50케이스 생성 스크립트
  validate_dataset.py    ← 구조 검증 + 카테고리 통계
  dataset_plan.md        ← 150케이스 설계 원본 계획서
```

> `intents_v2.jsonl`은 `generate_dataset.py`로 재생성 가능:
> ```bash
> cd endTOend/
> python data/generate_dataset.py
> python data/validate_dataset.py  # 검증
> ```
