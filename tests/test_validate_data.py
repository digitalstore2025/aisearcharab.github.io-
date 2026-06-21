from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "validate_data.py"
SPEC = importlib.util.spec_from_file_location("validate_data", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class DataValidationTest(unittest.TestCase):
    def test_repository_records_are_valid(self) -> None:
        self.assertEqual(MODULE.run(), [])

    def test_identifier_rule(self) -> None:
        self.assertIsNotNone(MODULE.ID_PATTERN.fullmatch("source-2026-01"))
        self.assertIsNone(MODULE.ID_PATTERN.fullmatch("Invalid ID"))


if __name__ == "__main__":
    unittest.main()
