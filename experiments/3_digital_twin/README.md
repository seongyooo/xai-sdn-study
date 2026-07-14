# Experiment 3 — Mininet Digital Twin

Static Validator를 통과한 ONOS FlowRule을 4-switch Mininet 토폴로지에 적용해
대상 트래픽 제어와 비대상 트래픽 보존을 자동 검증한다.

## 현재 머신 상태

- Docker daemon: 사용 가능
- Mininet / Open vSwitch: 설치 필요
- ONOS image: 최초 실행 시 다운로드 필요

## 1. 시스템 패키지 설치

Ubuntu/WSL2에서 실행한다.

```bash
sudo apt-get update
sudo apt-get install -y mininet openvswitch-switch python3-venv
sudo mn --test pingall
sudo mn -c
```

Mininet의 시스템 모듈을 함께 볼 수 있는 가상환경을 만든다.

```bash
cd experiments/3_digital_twin
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements.txt
```

## 2. ONOS 실행

```bash
cd experiments/3_digital_twin
docker compose up -d
docker compose logs -f onos
```

ONOS REST API가 준비됐는지 확인한다.

```bash
curl -u onos:rocks http://127.0.0.1:8181/onos/v1/devices
.venv/bin/python experiment.py --preflight
```

## 3. 실험 실행

```bash
sudo -E .venv/bin/python experiment.py
```

다른 ONOS 주소나 계정을 사용할 때:

```bash
export ONOS_USER=onos
export ONOS_PASSWORD=rocks
sudo -E .venv/bin/python experiment.py \
  --onos-url http://127.0.0.1:8181/onos/v1 \
  --controller-ip 127.0.0.1 \
  --controller-port 6653
```

실험은 priority `50000`을 전용 테스트 범위로 사용하며 종료 시 해당 테스트
FlowRule을 삭제한다. 공유/운영 ONOS가 아닌 이 실험 전용 컨테이너에서 실행해야 한다.

결과는 `results/digital_twin_<timestamp>.json`에 저장된다.

## 4. 코드 준비 검증

Mininet 설치 전에도 순수 Python 테스트와 구문 검사를 실행할 수 있다.

```bash
.venv/bin/python -m unittest -v test_experiment.py
.venv/bin/python -m py_compile experiment.py onos_client.py topology.py
docker compose config
```

## 정리

```bash
sudo mn -c
docker compose down
```
