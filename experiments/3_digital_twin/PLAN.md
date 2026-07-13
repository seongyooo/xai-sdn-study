# 실험 3 — Mininet Digital Twin 계획

> 작성: 2026-07-13
> 환경: WSL2 Ubuntu 22.04 + Docker 29.5.2

---

## 목표

실험 1(LLM FlowRule 생성) + 실험 2(Static Validator) 를 통과한 FlowRule을
ONOS 컨트롤러와 Mininet 가상 네트워크에 실제 배포하여 의도한 트래픽 제어가
동작하는지 검증한다.

---

## 전체 파이프라인

```
자연어 인텐트
    ↓ [실험 1] LLM + RAG
FlowRule JSON 생성
    ↓ [실험 2] Static Validator
스키마 검증 + 충돌 탐지
    ↓ [실험 3] Digital Twin ← 여기
ONOS에 배포 → Mininet 트래픽 테스트
    ↓ 성공 시
실제 ONOS 배포
```

---

## 실험 시나리오 (3가지)

| # | 자연어 인텐트 | 생성 FlowRule | 검증 방법 |
|---|-------------|--------------|----------|
| A | "h1에서 h2로 가는 트래픽을 포트 2로 포워딩" | OUTPUT port 2 | ping h1→h2 성공 |
| B | "h3에서 오는 모든 트래픽 차단" | DROP (IPV4_SRC=h3) | ping h3→h2 실패 |
| C | "h1→h2 TCP/80만 포트 2, 나머지는 DROP" | TCP_DST=80 + OUTPUT / else DROP | curl 성공, ping 실패 |

토폴로지: 스위치 1개(s1) + 호스트 3개(h1, h2, h3)

```
h1 ─┐
h2 ─┤── s1 ── ONOS Controller (Docker)
h3 ─┘
```

---

## 구현 단계

### Step 1: 환경 설치 (WSL2)
```bash
sudo apt-get install -y mininet openvswitch-switch
# 확인
sudo mn --test pingall
```

### Step 2: ONOS Docker 시작
```bash
docker pull onosproject/onos:2.7
docker run -d --name onos \
  -p 8181:8181 \   # REST API / Web UI
  -p 6653:6653 \   # OpenFlow
  onosproject/onos:2.7
# 앱 활성화 (Web UI 또는 CLI)
# openflow, fwd 앱 활성화 필요
```

### Step 3: Mininet 토폴로지 생성 (topology.py)
- RemoteController로 ONOS 연결
- 호스트 3개, 스위치 1개
- 스위치 DPID = ONOS deviceId와 매핑

### Step 4: FlowRule 배포 (deploy_and_test.py)
- ONOS REST API (POST /onos/v1/flows/{deviceId})
- 시나리오별 FlowRule JSON 순서대로 배포
- Mininet CLI에서 ping / iperf 테스트

---

## 평가 지표

| 지표 | 측정 방법 | 기대값 |
|------|----------|--------|
| FlowRule 배포 성공률 | REST API 201 응답 | 100% |
| 의도 달성률 | ping 결과 vs 기대 결과 | 100% |
| 오탐 없음 | 차단 의도인데 통과 | 0건 |

---

## 파일 구조

```
experiments/3_digital_twin/
  PLAN.md               ← 이 파일
  RESULTS.md            ← 실험 후 작성
  setup.sh              ← WSL2 환경 설치 스크립트
  topology.py           ← Mininet 토폴로지 정의
  deploy_and_test.py    ← 메인 실험: FlowRule 배포 + 트래픽 테스트
  scenarios/
    scenario_a.json     ← 포워딩 FlowRule
    scenario_b.json     ← DROP FlowRule
    scenario_c.json     ← TCP/80 선택 포워딩 FlowRule
```

---

## 선행 조건 체크리스트

- [x] WSL2 Ubuntu 22.04
- [x] Docker in WSL2
- [ ] Mininet 설치
- [ ] openvswitch-switch 설치
- [ ] ONOS Docker 이미지 pull
