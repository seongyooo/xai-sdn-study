"""Experiment 3: validate an ONOS FlowRule in a Mininet Digital Twin."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from onos_client import OnosClient, OnosError
from topology import EXPECTED_DEVICE_IDS, build_network


BASE_DIR = Path(__file__).resolve().parent
RESULTS_DIR = BASE_DIR / "results"
TEST_PRIORITY = 50000
DROP_RULE = {
    "flows": [
        {
            "priority": TEST_PRIORITY,
            "timeout": 0,
            "isPermanent": "true",
            "deviceId": "of:0000000000000001",
            "selector": {
                "criteria": [
                    {"type": "ETH_TYPE", "ethType": "0x800"},
                    {"type": "IP_PROTO", "protocol": 1},
                    {"type": "IPV4_SRC", "ip": "10.0.0.1/32"},
                    {"type": "IPV4_DST", "ip": "10.0.0.4/32"},
                ]
            },
        }
    ]
}


def validate_with_static_validator(payload: dict) -> None:
    validator_dir = BASE_DIR.parent / "2_static_validator"
    sys.path.insert(0, str(validator_dir))
    try:
        from validator import validate_flowrule
    finally:
        sys.path.pop(0)

    validation = validate_flowrule(payload)
    if not validation["valid"]:
        raise RuntimeError("Static Validator rejected test rule: " + "; ".join(validation["errors"]))


def ping_received(host, destination: str, count: int = 3) -> int:
    output = host.cmd(f"ping -c {count} -W 1 {destination}")
    match = re.search(r"(\d+)\s+(?:packets\s+)?received", output)
    return int(match.group(1)) if match else 0


def ping_reachable(host, destination: str, attempts: int = 2) -> bool:
    # The first attempt may install a reactive forwarding path.
    received = 0
    for _ in range(attempts):
        received = ping_received(host, destination)
        if received > 0:
            return True
    return False


def evaluate_checks(checks: dict[str, bool]) -> bool:
    return bool(checks) and all(checks.values())


def run_experiment(client: OnosClient, controller_ip: str, controller_port: int) -> dict:
    if os.geteuid() != 0:
        raise PermissionError("Mininet must run as root. Use sudo -E python3 experiment.py")

    validate_with_static_validator(DROP_RULE)
    client.wait_until_ready()
    client.activate_application("org.onosproject.fwd")

    net = build_network(controller_ip, controller_port)
    cleaned = 0
    try:
        net.start()
        client.wait_for_devices(EXPECTED_DEVICE_IDS)
        time.sleep(3)

        h1, h2 = net.get("h1", "h2")
        checks = {
            "four_switches_discovered": EXPECTED_DEVICE_IDS <= client.available_device_ids(),
            "baseline_h1_to_h4": ping_reachable(h1, "10.0.0.4"),
        }

        # Remove stale test rules from an interrupted earlier run.
        client.delete_flows_by_priority(TEST_PRIORITY)
        client.deploy_flow_rules(DROP_RULE)
        time.sleep(2)

        checks["target_h1_to_h4_blocked"] = not ping_reachable(h1, "10.0.0.4", attempts=1)
        checks["unrelated_h2_to_h3_reachable"] = ping_reachable(h2, "10.0.0.3")

        cleaned = client.delete_flows_by_priority(TEST_PRIORITY)
        time.sleep(2)
        checks["h1_to_h4_recovered"] = ping_reachable(h1, "10.0.0.4")

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": checks,
            "passed": evaluate_checks(checks),
            "test_priority": TEST_PRIORITY,
            "cleaned_test_flows": cleaned,
        }
    finally:
        try:
            client.delete_flows_by_priority(TEST_PRIORITY)
        except OnosError:
            pass
        net.stop()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--onos-url", default="http://127.0.0.1:8181/onos/v1")
    parser.add_argument("--onos-user", default=os.environ.get("ONOS_USER", "onos"))
    parser.add_argument("--onos-password", default=os.environ.get("ONOS_PASSWORD", "rocks"))
    parser.add_argument("--controller-ip", default="127.0.0.1")
    parser.add_argument("--controller-port", default=6653, type=int)
    parser.add_argument("--preflight", action="store_true", help="check ONOS only")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    client = OnosClient(args.onos_url, args.onos_user, args.onos_password)
    try:
        client.wait_until_ready(timeout=10 if args.preflight else 120)
        if args.preflight:
            print(f"ONOS ready; available devices: {len(client.available_device_ids())}")
            return 0

        result = run_experiment(client, args.controller_ip, args.controller_port)
    except (OnosError, PermissionError, RuntimeError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = int(time.time())
    output_path = RESULTS_DIR / f"digital_twin_{timestamp}.json"
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    for name, passed in result["checks"].items():
        print(f"[{'PASS' if passed else 'FAIL'}] {name}")
    print(f"Digital Twin validation: {'PASS' if result['passed'] else 'FAIL'}")
    print(f"Result: {output_path}")
    return 0 if result["passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
