"""
실험 3 — Digital Twin 메인 실험 스크립트

흐름:
  1. ONOS 준비 확인 (REST API)
  2. Mininet 토폴로지 시작
  3. 시나리오 A/B/C FlowRule 순서대로 배포
  4. ping / nc로 트래픽 테스트
  5. 결과 저장

실행 방법:
  sudo python3 deploy_and_test.py
"""

import os
import sys
import json
import time
import requests
from requests.auth import HTTPBasicAuth

# ── Mininet import (WSL2/Linux에서만 가능) ─────────────────
try:
    from mininet.net import Mininet
    from mininet.node import RemoteController, OVSSwitch
    from mininet.link import TCLink
    from mininet.log import setLogLevel
    MININET_AVAILABLE = True
except ImportError:
    MININET_AVAILABLE = False
    print("[경고] Mininet을 찾을 수 없습니다. WSL2에서 실행하세요.")

# ── 설정 ───────────────────────────────────────────────────
ONOS_REST  = "http://127.0.0.1:8181/onos/v1"
ONOS_AUTH  = HTTPBasicAuth("onos", "rocks")
DEVICE_ID  = "of:0000000000000001"

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
SCENARIOS_DIR = os.path.join(BASE_DIR, "scenarios")
RESULTS_DIR   = os.path.join(BASE_DIR, "results")
os.makedirs(RESULTS_DIR, exist_ok=True)


# ── ONOS 연결 확인 ─────────────────────────────────────────

def wait_for_onos(timeout=60):
    print("ONOS 시작 대기 중...", end="", flush=True)
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(f"{ONOS_REST}/devices", auth=ONOS_AUTH, timeout=3)
            if r.status_code == 200:
                print(" 연결됨!")
                return True
        except Exception:
            pass
        print(".", end="", flush=True)
        time.sleep(3)
    print(" 타임아웃!")
    return False


def wait_for_device(timeout=60):
    """Mininet 스위치가 ONOS에 등록될 때까지 대기"""
    print(f"디바이스 {DEVICE_ID} 등록 대기 중...", end="", flush=True)
    start = time.time()
    while time.time() - start < timeout:
        try:
            r = requests.get(f"{ONOS_REST}/devices/{DEVICE_ID}", auth=ONOS_AUTH, timeout=3)
            if r.status_code == 200:
                print(" 등록됨!")
                return True
        except Exception:
            pass
        print(".", end="", flush=True)
        time.sleep(2)
    print(" 타임아웃!")
    return False


# ── FlowRule 관리 ──────────────────────────────────────────

def clear_flows():
    """기존 FlowRule 모두 삭제"""
    try:
        r = requests.delete(
            f"{ONOS_REST}/flows/application/org.onosproject.rest",
            auth=ONOS_AUTH, timeout=5
        )
        print(f"  기존 FlowRule 삭제: {r.status_code}")
    except Exception as e:
        print(f"  FlowRule 삭제 실패: {e}")


def deploy_flows(scenario_file: str) -> dict:
    """시나리오 JSON의 FlowRule을 ONOS에 배포"""
    with open(scenario_file, encoding="utf-8") as f:
        data = json.load(f)

    flows = data.get("flows", [])
    results = []

    for flow in flows:
        # deviceId를 실제 값으로 교체
        flow["deviceId"] = DEVICE_ID
        payload = {"flows": [flow]}

        try:
            r = requests.post(
                f"{ONOS_REST}/flows",
                json=payload,
                auth=ONOS_AUTH,
                timeout=10
            )
            success = r.status_code in (200, 201)
            results.append({
                "priority": flow.get("priority"),
                "status_code": r.status_code,
                "success": success,
            })
            status = "OK" if success else "FAIL"
            print(f"  [{status}] priority={flow.get('priority')} → HTTP {r.status_code}")
        except Exception as e:
            results.append({"priority": flow.get("priority"), "error": str(e), "success": False})
            print(f"  [FAIL] priority={flow.get('priority')} → {e}")

    return {
        "scenario": os.path.basename(scenario_file),
        "total": len(flows),
        "success": sum(1 for r in results if r["success"]),
        "details": results,
    }


# ── 트래픽 테스트 ──────────────────────────────────────────

def ping_test(src, dst, count=3):
    """Mininet 호스트 간 ping 테스트"""
    result = src.cmd(f"ping -c {count} -W 1 {dst.IP()}")
    received = int([l for l in result.split("\n") if "received" in l][0].split()[3])
    success = received > 0
    return {
        "src": src.name,
        "dst": dst.name,
        "dst_ip": dst.IP(),
        "sent": count,
        "received": received,
        "success": success,
    }


def tcp_test(src, dst, port=80):
    """TCP 연결 테스트 (nc 사용)"""
    # dst에 서버 띄우기
    dst.cmd(f"nc -lk {port} &")
    time.sleep(0.5)
    result = src.cmd(f"nc -zw1 {dst.IP()} {port} && echo OK || echo FAIL")
    dst.cmd(f"kill %nc 2>/dev/null")
    success = "OK" in result
    return {
        "src": src.name,
        "dst": dst.name,
        "port": port,
        "success": success,
    }


# ── 시나리오별 테스트 ──────────────────────────────────────

def run_scenario_a(net, h1, h2, h3):
    """시나리오 A: h1→h2 포워딩"""
    print("\n[시나리오 A] h1→h2 포워딩 테스트")
    time.sleep(2)  # FlowRule 적용 대기
    r = ping_test(h1, h2)
    status = "OK (의도 달성)" if r["success"] else "FAIL"
    print(f"  h1 → h2 ping: {r['received']}/{r['sent']} [{status}]")
    return {"scenario": "A", "intent": "h1→h2 포워딩", "tests": [r],
            "intent_achieved": r["success"]}


def run_scenario_b(net, h1, h2, h3):
    """시나리오 B: h3 차단"""
    print("\n[시나리오 B] h3 차단 테스트")
    time.sleep(2)
    r1 = ping_test(h3, h2)
    r2 = ping_test(h1, h2)  # h1→h2는 여전히 가능해야 함
    blocked_ok = not r1["success"]
    forward_ok = r2["success"]
    status = "OK (의도 달성)" if (blocked_ok and forward_ok) else "FAIL"
    print(f"  h3 → h2 ping (차단 확인): {'차단됨' if blocked_ok else '통과됨'} [{status}]")
    print(f"  h1 → h2 ping (정상 확인): {'성공' if forward_ok else '실패'}")
    return {"scenario": "B", "intent": "h3 차단",
            "tests": [r1, r2], "intent_achieved": blocked_ok and forward_ok}


def run_scenario_c(net, h1, h2, h3):
    """시나리오 C: TCP/80만 허용, 나머지 DROP"""
    print("\n[시나리오 C] TCP/80 선택 포워딩 테스트")
    time.sleep(2)
    tcp_r = tcp_test(h1, h2, port=80)
    ping_r = ping_test(h1, h2)  # ICMP → DROP 돼야 함
    tcp_ok = tcp_r["success"]
    ping_blocked = not ping_r["success"]
    status = "OK (의도 달성)" if (tcp_ok and ping_blocked) else "FAIL"
    print(f"  h1 → h2 TCP/80: {'성공' if tcp_ok else '실패'}")
    print(f"  h1 → h2 ICMP ping (차단 확인): {'차단됨' if ping_blocked else '통과됨'} [{status}]")
    return {"scenario": "C", "intent": "TCP/80만 허용",
            "tests": [tcp_r, ping_r], "intent_achieved": tcp_ok and ping_blocked}


# ── 메인 ───────────────────────────────────────────────────

def main():
    if not MININET_AVAILABLE:
        print("WSL2/Linux 환경에서 실행하세요: sudo python3 deploy_and_test.py")
        sys.exit(1)

    setLogLevel("warning")

    # 1. ONOS 연결 확인
    if not wait_for_onos():
        print("ONOS에 연결할 수 없습니다.")
        print("ONOS 시작: docker run -d --name onos -p 8181:8181 -p 6653:6653 onosproject/onos:2.7")
        sys.exit(1)

    # 2. Mininet 시작
    from topology import create_topology
    net, s1, h1, h2, h3 = create_topology()

    # 3. 디바이스 등록 확인
    if not wait_for_device():
        print("스위치가 ONOS에 등록되지 않았습니다.")
        net.stop()
        sys.exit(1)

    all_results = []

    try:
        # ── 시나리오 A ─────────────────────────────────────
        print("\n" + "="*60)
        print("시나리오 A: h1→h2 포워딩")
        print("="*60)
        clear_flows()
        deploy_result_a = deploy_flows(os.path.join(SCENARIOS_DIR, "scenario_a.json"))
        test_result_a = run_scenario_a(net, h1, h2, h3)
        all_results.append({**deploy_result_a, **test_result_a})

        # ── 시나리오 B ─────────────────────────────────────
        print("\n" + "="*60)
        print("시나리오 B: h3 차단")
        print("="*60)
        clear_flows()
        deploy_result_b = deploy_flows(os.path.join(SCENARIOS_DIR, "scenario_b.json"))
        test_result_b = run_scenario_b(net, h1, h2, h3)
        all_results.append({**deploy_result_b, **test_result_b})

        # ── 시나리오 C ─────────────────────────────────────
        print("\n" + "="*60)
        print("시나리오 C: TCP/80 선택 포워딩")
        print("="*60)
        clear_flows()
        deploy_result_c = deploy_flows(os.path.join(SCENARIOS_DIR, "scenario_c.json"))
        test_result_c = run_scenario_c(net, h1, h2, h3)
        all_results.append({**deploy_result_c, **test_result_c})

    finally:
        net.stop()

    # ── 최종 결과 출력 ─────────────────────────────────────
    print("\n" + "="*60)
    print("실험 3 결과 요약")
    print("="*60)
    total = len(all_results)
    achieved = sum(1 for r in all_results if r.get("intent_achieved"))
    deploy_ok = sum(r["success"] for r in all_results)
    deploy_total = sum(r["total"] for r in all_results)

    print(f"FlowRule 배포 성공률: {deploy_ok}/{deploy_total} "
          f"({deploy_ok/deploy_total*100:.0f}%)")
    print(f"의도 달성률:          {achieved}/{total} "
          f"({achieved/total*100:.0f}%)")
    print("-"*60)
    for r in all_results:
        icon = "OK" if r.get("intent_achieved") else "FAIL"
        print(f"  [{icon}] 시나리오 {r['scenario']}: {r.get('intent', '')}")

    # ── 결과 저장 ──────────────────────────────────────────
    output = {
        "timestamp": int(time.time()),
        "deploy_success_rate": deploy_ok / deploy_total * 100,
        "intent_achievement_rate": achieved / total * 100,
        "scenarios": all_results,
    }
    path = os.path.join(RESULTS_DIR, f"exp3_{int(time.time())}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    print(f"\n결과 저장: {path}")


if __name__ == "__main__":
    main()
