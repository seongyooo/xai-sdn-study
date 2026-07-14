import unittest

from experiment import DROP_RULE, TEST_PRIORITY, evaluate_checks
from onos_client import OnosClient
from topology import EXPECTED_DEVICE_IDS


class ExperimentPreparationTests(unittest.TestCase):
    def test_expected_device_ids_match_ibnbench(self):
        self.assertEqual(
            EXPECTED_DEVICE_IDS,
            {f"of:{number:016x}" for number in range(1, 5)},
        )

    def test_drop_rule_is_scoped_and_has_no_treatment(self):
        rule = DROP_RULE["flows"][0]
        self.assertEqual(rule["priority"], TEST_PRIORITY)
        self.assertNotIn("treatment", rule)
        criteria = {item["type"]: item for item in rule["selector"]["criteria"]}
        self.assertEqual(criteria["IPV4_SRC"]["ip"], "10.0.0.1/32")
        self.assertEqual(criteria["IPV4_DST"]["ip"], "10.0.0.4/32")
        self.assertEqual(criteria["IP_PROTO"]["protocol"], 1)

    def test_evaluation_requires_every_check(self):
        self.assertTrue(evaluate_checks({"a": True, "b": True}))
        self.assertFalse(evaluate_checks({"a": True, "b": False}))
        self.assertFalse(evaluate_checks({}))

    def test_client_rejects_empty_flow_payload(self):
        with self.assertRaises(ValueError):
            OnosClient().deploy_flow_rules({"flows": []})


if __name__ == "__main__":
    unittest.main()
