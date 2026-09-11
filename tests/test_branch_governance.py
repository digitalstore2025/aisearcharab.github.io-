import unittest

from scripts.verify_branch_governance import GovernanceError, validate_branch_payload


VALID_SHA = "5a55544a92cb4315b9419ff4159d768b204b5b55"


class BranchGovernanceTests(unittest.TestCase):
    def test_protected_main_passes_minimum_floor(self):
        result = validate_branch_payload(
            {"name": "main", "protected": True, "commit": {"sha": VALID_SHA}}
        )
        self.assertTrue(result["protected"])
        self.assertEqual(result["minimum_governance_floor"], "PASS")
        self.assertFalse(result["production_ready"])

    def test_unprotected_main_fails_closed(self):
        with self.assertRaisesRegex(GovernanceError, "main_is_not_protected"):
            validate_branch_payload(
                {"name": "main", "protected": False, "commit": {"sha": VALID_SHA}}
            )

    def test_missing_protected_field_fails_closed(self):
        with self.assertRaisesRegex(GovernanceError, "main_is_not_protected"):
            validate_branch_payload({"name": "main", "commit": {"sha": VALID_SHA}})

    def test_wrong_branch_fails_closed(self):
        with self.assertRaisesRegex(GovernanceError, "unexpected_branch_payload"):
            validate_branch_payload(
                {"name": "develop", "protected": True, "commit": {"sha": VALID_SHA}}
            )

    def test_invalid_commit_sha_fails_closed(self):
        with self.assertRaisesRegex(GovernanceError, "invalid_commit_sha"):
            validate_branch_payload(
                {"name": "main", "protected": True, "commit": {"sha": "not-a-sha"}}
            )


if __name__ == "__main__":
    unittest.main()
