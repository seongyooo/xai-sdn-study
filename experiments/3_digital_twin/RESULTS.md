# 실험 3 — Mininet Digital Twin 결과

> 실험 일시: 2026-07-13
> 환경: WSL2 Ubuntu 22.04 + Docker (ONOS 3.0.0) + Mininet

---

## 요약

| 지표 | 결과 |
|------|------|
| FlowRule 배포 성공률 | **100%** (4/4) |
| 의도 달성률 | **100%** (3/3 시나리오) |

---

## 실험 환경

```
토폴로지: 스위치 1개(s1) + 호스트 3개(h1, h2, h3)

h1 (10.0.0.1) ─ port1 ┐
h2 (10.0.0.2) ─ port2 ┤── s1 (of:0000000000000001) ── ONOS 3.0.0 (Docker)
h3 (10.0.0.3) ─ port3 ┘

컨트롤러: ONOS 3.0.0-SNAPSHOT (onosproject/onos:latest)
          REST API: http://localhost:8181
          OpenFlow: localhost:6653
활성화 앱: org.onosproject.openflow, org.onosproject.fwd
```

---

## 시나리오별 결과

### 시나리오 A — 포워딩 (FORWARD)

**자연어 인텐트:** "h1에서 h2로 가는 트래픽을 포트 2로 포워딩"

**생성된 FlowRule:**
```json
{
  "priority": 200,
  "selector": {
    "criteria": [
      { "type": "ETH_TYPE", "ethType": "0x800" },
      { "type": "IPV4_DST", "ip": "10.0.0.2/32" }
    ]
  },
  "treatment": { "instructions": [{ "type": "OUTPUT", "port": "2" }] }
}
```

**검증 결과:**

| 테스트 | 송신 | 수신 | 결과 |
|--------|------|------|------|
| h1 → h2 ping | 3 | 3 | **성공** |

→ 의도 달성: **OK**

---

### 시나리오 B — 차단 (DROP)

**자연어 인텐트:** "h3에서 오는 모든 트래픽 차단"

**생성된 FlowRule:**
```json
{
  "priority": 300,
  "selector": {
    "criteria": [
      { "type": "ETH_TYPE", "ethType": "0x800" },
      { "type": "IPV4_SRC", "ip": "10.0.0.3/32" }
    ]
  },
  "treatment": { "instructions": [] }
}
```

**검증 결과:**

| 테스트 | 송신 | 수신 | 결과 |
|--------|------|------|------|
| h3 → h2 ping (차단 확인) | 3 | 0 | **차단됨** |
| h1 → h2 ping (정상 확인) | 3 | 3 | **성공** |

→ h3 트래픽만 선택적으로 차단, h1 정상 통신 유지: **OK**

---

### 시나리오 C — 선택적 포워딩 (TCP/80만 허용)

**자연어 인텐트:** "h1→h2 TCP 포트 80 트래픽만 허용, 나머지 차단"

**생성된 FlowRule (2개):**
```json
[
  {
    "priority": 400,
    "selector": {
      "criteria": [
        { "type": "ETH_TYPE", "ethType": "0x800" },
        { "type": "IP_PROTO", "protocol": 6 },
        { "type": "IPV4_DST", "ip": "10.0.0.2/32" },
        { "type": "TCP_DST", "tcpPort": 80 }
      ]
    },
    "treatment": { "instructions": [{ "type": "OUTPUT", "port": "2" }] }
  },
  {
    "priority": 100,
    "selector": {
      "criteria": [
        { "type": "ETH_TYPE", "ethType": "0x800" },
        { "type": "IPV4_DST", "ip": "10.0.0.2/32" }
      ]
    },
    "treatment": { "instructions": [] }
  }
]
```

**검증 결과:**

| 테스트 | 결과 |
|--------|------|
| h1 → h2 TCP/80 (nc) | **성공** |
| h1 → h2 ICMP ping (차단 확인) | **차단됨** |

→ 프로토콜/포트 단위 세밀한 트래픽 제어 동작 확인: **OK**

---

## 전체 파이프라인 동작 확인

```
자연어 인텐트
    ↓ [실험 1] LLM + RAG → FlowRule JSON 생성
    ↓ [실험 2] Static Validator → 스키마 검증 + 충돌 탐지
    ↓ [실험 3] Digital Twin → ONOS 배포 + 트래픽 검증  ← 100% 달성
```

3단계 파이프라인이 시나리오 A/B/C 모두에서 오류 없이 동작함을 확인.

---

## NetIntent와 비교

| 기능 | NetIntent | 우리 시스템 |
|------|-----------|-------------|
| FlowRule 생성 | LLM (few-shot) | LLM + RAG |
| 스키마 검증 | 기본 | Pydantic 전체 검증 |
| 충돌 탐지 | LLM 기반 | LLM + Rule-based (98.6%) |
| **가상 네트워크 검증** | **없음** | **Mininet + ONOS (100%)** |
| 충돌 이유 설명 | 없음 | 자연어 설명 생성 |

---

## 논문 활용 포인트

> "생성된 FlowRule은 Static Validator(실험 2) 통과 후 Mininet 기반 Digital Twin에
> 자동 배포되어 동작을 검증한다. 포워딩, 차단, 선택적 포워딩 3가지 시나리오에서
> FlowRule 배포 성공률 100%, 의도 달성률 100%를 달성하였다."

---

## 결과 파일

```
experiments/3_digital_twin/results/
  exp3_1783932934.json    ← 전체 실험 결과 (JSON)
```
