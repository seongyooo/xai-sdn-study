# Explainable-and-DT-Validated-LLM-RAG-Framework-for-Safe-Intent-Driven-SDN-Automation

> 클론한 GitHub 레포 내용 정리 (폴더 삭제 전 아카이브)
> 원본: [GitHub 레포](https://github.com/search?q=Explainable-and-DT-Validated-LLM-RAG-Framework-for-Safe-Intent-Driven-SDN-Automation)

---

## 프로젝트 개요

**목표**: Digital Twin 검증 + XAI 설명이 결합된 LLM/RAG 기반 안전한 Intent-Driven SDN 자동화 시스템

LLM으로 SDN 정책을 생성하는 것에 그치지 않고, 사람이 검증·설명 가능한 형태로 안전하게 적용하는 것이 핵심.

### 제안 파이프라인

```
사용자 인텐트 (자연어 입력)
→ LLM/RAG가 인텐트 해석
→ SDN 정책 후보 생성
→ Static Validator (룰 충돌 정적 검사)
→ Digital Twin (실제 네트워크 적용 전 시뮬레이션 검증)
→ XAI Layer (판단 근거 설명)
→ 안전한 경우에만 실제 컨트롤러(Ryu/ONOS)에 적용
```

### 기술 스택

| 구성 요소 | 기술 |
|-----------|------|
| 언어 | Python 3.11 |
| SDN 컨트롤러 | ONOS 2.7 (Docker) |
| 네트워크 시뮬레이터 | Mininet |
| 소프트웨어 스위치 | Open vSwitch (OpenFlow 1.3) |
| 가상화 | KVM / libvirt / virt-manager |
| 패키지 관리 | uv |

---

## 폴더 구조

```
.
├── .gitignore
├── .python-version          # Python 3.11
├── README.md
├── main.py                  # placeholder (Hello from safe-intent-sdn!)
├── pyproject.toml           # 패키지명: safe-intent-sdn, v0.1.0
├── uv.lock
├── experiments/
│   ├── 0_Project_Overview.md
│   ├── 1_setup.md
│   └── 2_basic_sdn_test.md
├── logs/
│   └── .gitkeep
└── scripts/
    ├── start_onos.sh
    └── start_mn_single3.sh
```

---

## 파일별 내용

### main.py

```python
def main():
    print("Hello from safe-intent-sdn!")

if __name__ == "__main__":
    main()
```

현재 placeholder 상태. 실제 구현 미완.

---

### pyproject.toml

```toml
[project]
name = "safe-intent-sdn"
version = "0.1.0"
description = "Add your description here"
readme = "README.md"
requires-python = ">=3.11"
dependencies = []
```

외부 의존성 없음 (초기 단계).

---

### experiments/0_Project_Overview.md — 프로젝트 개요

**연구 배경**:
- 네트워크는 AI/Agent/Digital Twin을 활용한 Zero-Touch 자동화 방향으로 전환 중
- LLM 기반 네트워크 관리의 한계: 환각(Hallucination), 도메인 적응 부족, 잘못된 설정 생성
- 해결 방안: RAG(컨텍스트 주입) + Static Validator + Digital Twin + XAI

**기존 SDN 운영의 수동 단계**:
1. 네트워크 상태 모니터링
2. 병목/장애 분석
3. 정책 생성
4. OpenFlow 룰 적용
5. 적용 후 검증

---

### experiments/1_setup.md — 실험 환경 구축

**호스트 환경**: Arch Linux + KVM + libvirt + virt-manager

**Ubuntu 24.04 VM 권장 스펙**:
- 4 vCPU, 8GB RAM, 50GB 디스크
- 가상 네트워크: default NAT

**설치 패키지** (Ubuntu VM 내):
```
mininet, openvswitch-switch, iperf3, tcpdump, git, curl, docker.io, openjdk-17-jdk
```

**ONOS 실행** (Docker):
```bash
docker run -d --name onos --network host onosproject/onos:2.7-latest
```
- Web UI: http://localhost:8181/onos/ui (ID: onos / PW: rocks)
- 활성화 앱: `org.onosproject.openflow`, `org.onosproject.fwd`

**최종 아키텍처**:
```
Mininet Hosts (h1, h2, h3)
       ↓
Open vSwitch s1 (OpenFlow 1.3)
       ↓
ONOS Controller
```

---

### experiments/2_basic_sdn_test.md — Day 1 실험 결과

**테스트 환경**:
- 컨트롤러: ONOS 2.7 (Docker, --network host)
- 토폴로지: single,3 (스위치 1개, 호스트 3개)
- 프로토콜: OpenFlow 1.3 (포트 6653)

**결과 요약**:

| 항목 | 결과 |
|------|------|
| ONOS 기동 | 성공 |
| OpenFlow 앱 활성화 | 성공 |
| Mininet 연결 | 성공 |
| pingall | 0% 패킷 손실 |

**토폴로지**:
```
h1 ──┐
h2 ──┼── s1 (OVS, OF1.3) ── ONOS Controller (6653)
h3 ──┘
```

---

### scripts/start_onos.sh

```bash
#!/bin/bash
docker rm -f onos 2>/dev/null
docker run -d \
  --name onos \
  --network host \
  onosproject/onos:2.7-latest
sleep 15
docker exec -it onos /root/onos/bin/onos-app localhost activate org.onosproject.openflow
docker exec -it onos /root/onos/bin/onos-app localhost activate org.onosproject.fwd
sudo ss -lntp | grep 6653
```

---

### scripts/start_mn_single3.sh

```bash
#!/bin/bash
sudo mn -c
sudo mn \
  --topo single,3 \
  --controller remote,ip=127.0.0.1,port=6653 \
  --switch ovsk,protocols=OpenFlow13
```

---

## 현재 구현 상태 (v0.1.0)

- [x] SDN 테스트베드 환경 구축 (ONOS + Mininet + OpenFlow 1.3)
- [x] 기본 연결성 검증 (pingall 0% loss)
- [ ] LLM/RAG 시스템 구현
- [ ] Static Validator 구현
- [ ] Digital Twin 연동
- [ ] XAI Layer 구현
