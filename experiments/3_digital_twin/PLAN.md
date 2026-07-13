# 실험 3 — Mininet Digital Twin 계획

## 목표

Static Validator를 통과한 ONOS FlowRule을 실제 컨트롤러에 배포하기 전에
Mininet으로 복제한 네트워크에서 검증한다.

## 토폴로지

IBNBench ONOS 예제와 동일한 4-switch diamond 토폴로지를 사용한다.

```text
h1(10.0.0.1) -- s1 -- s2 -- s4 -- h3(10.0.0.3)
                  \       /       -- h4(10.0.0.4)
                   s3 ---
h2(10.0.0.2) -- s1
```

- DPID: `of:0000000000000001` ~ `of:0000000000000004`
- OpenFlow: 1.3
- 상단 경로(s1-s2-s4): 1 Mbps
- 하단 경로(s1-s3-s4): 10 Mbps

## 검증 시나리오

1. ONOS 준비 상태와 4개 스위치 연결을 확인한다.
2. Reactive Forwarding 앱을 활성화하고 baseline ping을 확인한다.
3. 실험 2의 Pydantic Validator로 테스트 DROP 규칙을 검사한다.
4. h1→h4 ICMP DROP 규칙을 ONOS REST API로 배포한다.
5. 대상 트래픽은 차단되고 h2→h3 비대상 트래픽은 유지되는지 확인한다.
6. 테스트 규칙을 삭제하고 h1→h4 연결이 복구되는지 확인한다.

## 성공 기준

| 지표 | 성공 기준 |
|---|---|
| 스위치 발견 | 4/4 |
| Baseline h1→h4 | 성공 |
| 정책 적용 h1→h4 | 차단 |
| 정책 적용 h2→h3 | 성공 |
| Cleanup 후 h1→h4 | 성공 |
| 정책 검증 통과율 | 100% |

모든 조건을 만족해야 Digital Twin 검증을 통과한 것으로 판정한다.
