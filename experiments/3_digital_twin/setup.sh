#!/bin/bash
# WSL2 Ubuntu 22.04 환경 설치 스크립트
# 실행: bash setup.sh

set -e

echo "=== Step 1: Mininet + OVS 설치 ==="
sudo apt-get update -q
sudo apt-get install -y mininet openvswitch-switch

echo ""
echo "=== Step 2: OVS 서비스 시작 ==="
sudo service openvswitch-switch start

echo ""
echo "=== Step 3: Mininet 동작 확인 ==="
sudo mn --test pingall 2>&1 | tail -5

echo ""
echo "=== Step 4: ONOS Docker 이미지 pull ==="
docker pull onosproject/onos:2.7

echo ""
echo "=== 설치 완료 ==="
echo "다음 명령으로 실험 시작:"
echo "  python3 deploy_and_test.py"
