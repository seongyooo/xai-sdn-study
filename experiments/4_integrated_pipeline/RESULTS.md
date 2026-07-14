# 통합 파이프라인 실험 결과

> 실험 일시: 2026-07-14
> run_id: 20260714T033627Z
> 모델: gemini-3.1-flash-lite (생성 + 임베딩)
> 데이터셋: IBNBench Intent2Flow-ONOS (50쌍, 25 train / 25 test)
> RAG k=3

---

## 파이프라인 개요

자연어 인텐트 → FlowRule 생성 → 정적 검증 → 디지털 트윈 배포 검증까지
End-to-End로 자동 실행하는 통합 파이프라인.

```
[Stage 1] RAG 기반 FlowRule 생성
    ↓ 25개 FlowRule JSON
[Stage 2a] Pydantic 스키마 검증
    ↓ 24개 통과 / 1개 탈락
[Stage 2b] LLM 충돌 탐지 (50쌍)
    ↓ 4건 충돌 발견
[Stage 2c] XAI 충돌 설명 생성
    ↓ 4건 설명 생성
[Stage 3] Mininet Digital Twin 검증
    ↓ 5/5 PASS
```

---

## Stage 1: RAG FlowRule 생성

| 항목 | 결과 |
|------|------|
| 방식 | RAG k=3 (gemini-embedding-001 + FAISS) |
| 테스트 인텐트 수 | 25 |
| 정확 생성 | 24 |
| **정확도** | **96.0%** |

### 실패 케이스 (1건)

**인텐트:**
> "Route HTTP traffic originating from 192.168.1.2 on port 1 of switch 4 and destined for 10.0.0.5/32 through port 2, ensuring packets are assigned to queue 0 for low-latency processing and apply VLAN tag 100."

**원인:** VLAN 태그 + QoS 복합 액션 처리 오류. 정답은 `L2MODIFICATION/VLAN_ID` 방식이지만, LLM이 존재하지 않는 `PUSH_VLAN` + `SET_VLAN_ID` instruction type을 생성(환각).

또한 TCP 방향 혼동: 정답은 `TCP_DST` 포트 80이지만 LLM은 `TCP_SRC`로 생성.

---

## Stage 2a: 스키마 검증

| 항목 | 결과 |
|------|------|
| 검증 대상 | 25개 (Stage 1 생성 전체) |
| **통과** | **24개** |
| **탈락** | **1개** |

### 탈락 케이스 (1건)

Stage 1 실패 케이스와 동일. 검증기가 환각 instruction type을 정확히 탐지:

```
[flows → 0 → treatment → instructions → 0 → type]
  알 수 없는 instruction type: 'PUSH_VLAN'. LLM 환각 의심.

[flows → 0 → treatment → instructions → 1 → type]
  알 수 없는 instruction type: 'SET_VLAN_ID'. LLM 환각 의심.
```

→ Pydantic 스키마 검증이 LLM 환각을 자동으로 필터링하여 배포 전 차단.

---

## Stage 2b: 충돌 탐지

| 항목 | 결과 |
|------|------|
| 검사 대상 | valid 24개 중 50쌍 |
| **충돌 발견** | **4건** |
| 충돌 없음 | 46건 |

### 충돌 목록

| # | 인텐트 A | 인텐트 B | 충돌 유형 |
|---|---------|---------|---------|
| 1 | Route default traffic of node 4 via interface 1 | Drop all packets from 10.0.0.1 to 10.0.0.4 using node 4 | **Imbrication** |
| 2 | Route default traffic of node 4 via interface 1 | Prioritize blocking packets from 10.0.0.1 to 10.0.0.4 in node 4 | **Shadowing** |
| 3 | Route default traffic of node 4 via interface 1 | In switch 4, block all IPv4 traffic from 10.0.0.1 to 10.0.0.4 | **Shadowing** |
| 4 | Route default traffic of node 4 via interface 1 | Prioritize routing SNMP traffic (UDP port 161) to port 5 of switch 4 | **Shadowing** |

**패턴 분석:** 4건 모두 switch 4의 광범위한 기본 라우팅 규칙(priority 10, ETH_TYPE만 매칭)과 더 구체적인 고우선순위 규칙 간 충돌. 기본 경로 규칙이 동일 디바이스의 특정 규칙들과 중첩 발생.

---

## Stage 2c: XAI 충돌 설명

충돌 4건에 대해 자연어 설명 자동 생성. 주요 내용 요약:

### 충돌 1 — Imbrication (규칙 #0 vs #8)
- **왜:** FlowRule 2(DROP)가 FlowRule 1(기본 라우팅)의 부분집합. 같은 디바이스에서 ETH_TYPE 0x800을 공유하나 FlowRule 2가 IP 주소를 추가로 제한.
- **영향:** FlowRule 2의 높은 우선순위(200 > 10)로 인해 특정 IP 쌍 트래픽이 기본 경로 대신 DROP 처리됨.
- **조치:** 특정 규칙은 항상 기본 규칙보다 높은 우선순위를 갖도록 명시적 계층 설계 필요.

### 충돌 2, 3 — Shadowing (규칙 #0 vs #10, #11)
- **왜:** 고우선순위 방화벽 규칙(priority 500)이 기본 라우팅 규칙(priority 10)을 shadow. 동일 디바이스에서 ETH_TYPE 0x800 트래픽이 겹침.
- **영향:** 10.0.0.1→10.0.0.4 트래픽은 FlowRule 2에서 처리되어 DROP. 나머지 IPv4는 FlowRule 1로 포워딩.
- **조치:** 방화벽 규칙에 명시적 treatment(OUTPUT 또는 DROP) 추가 권장.

### 충돌 4 — Shadowing (규칙 #0 vs #17)
- **왜:** SNMP 특화 규칙(UDP port 161, priority 300)이 기본 IPv4 라우팅 규칙과 겹침.
- **영향:** SNMP 트래픽은 port 5로, 나머지는 port 1으로 분리 라우팅.
- **조치:** 기본 경로 규칙의 의도를 명확히 하고, 특수 트래픽 규칙과의 우선순위 계층 문서화 필요.

---

## Stage 3: Digital Twin 검증

| 체크 항목 | 결과 |
|----------|------|
| four_switches_discovered | PASS |
| baseline_h1_to_h4 | PASS |
| target_h1_to_h4_blocked | PASS |
| unrelated_h2_to_h3_reachable | PASS |
| h1_to_h4_recovered | PASS |
| **종합** | **5/5 PASS** |

- 토폴로지: 4-switch 다이아몬드 (s1-s2/s3-s4), 4 호스트
- 배포한 규칙: DROP rule (h1→h4 ICMP, priority 50000)
- 인텐트 달성: DROP 룰 적용 후 h1→h4 차단, h2→h3 무영향, 룰 삭제 후 복구 확인

---

## 전체 요약

| 단계 | 지표 | 값 |
|------|------|-----|
| Stage 1 생성 정확도 | 25개 중 정확 생성 | **96.0%** (24/25) |
| Stage 2a 스키마 통과율 | 유효 FlowRule | **96.0%** (24/25) |
| Stage 2b 충돌 탐지 | 50쌍 검사 | **4건 충돌** (Shadowing×3, Imbrication×1) |
| Stage 2c XAI 설명 | 충돌별 설명 | **4건 생성** |
| Stage 3 Digital Twin | 5개 체크 | **5/5 PASS** |

### 핵심 발견

1. **RAG 96% 정확도 유지**: 개별 실험(Exp 1)과 동일한 성능이 통합 파이프라인에서도 재현됨.

2. **스키마 검증의 유효성**: LLM이 VLAN 처리에서 존재하지 않는 instruction type(PUSH_VLAN, SET_VLAN_ID)을 생성했고, Pydantic 검증기가 이를 자동 탐지·차단. 배포 전 필터링 효과 입증.

3. **충돌 패턴**: 광범위한 기본 라우팅 규칙과 구체적 고우선순위 규칙 공존 시 Shadowing/Imbrication 발생. 동일 디바이스에서 ETH_TYPE만 매칭하는 catch-all 규칙 사용 시 주의 필요.

4. **End-to-End 검증 성공**: 생성 → 정적 검증 → 디지털 트윈 배포까지 전 과정 자동 실행 및 5/5 PASS 달성.
