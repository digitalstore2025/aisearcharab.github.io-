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
    """Test suite for data validation."""

    def test_repository_records_are_valid(self) -> None:
        """Test that all existing records in the repository are valid."""
        self.assertEqual(MODULE.run(), [])

    def test_identifier_pattern_valid(self) -> None:
        """Test valid kebab-case identifiers."""
        valid_ids = [
            "source-2026-01",
            "claim-basic",
            "entity-person-001",
            "a",
            "a-b",
            "a-b-c-d-e",
            "x123-y456",
        ]
        for vid in valid_ids:
            self.assertIsNotNone(
                MODULE.ID_PATTERN.fullmatch(vid),
                f"Expected '{vid}' to be valid"
            )

    def test_identifier_pattern_invalid(self) -> None:
        """Test invalid identifiers."""
        invalid_ids = [
            "Invalid ID",
            "UPPERCASE",
            "with_underscore",
            "with.dot",
            "trailing-",
            "-leading",
            "",
        ]
        for iid in invalid_ids:
            self.assertIsNone(
                MODULE.ID_PATTERN.fullmatch(iid),
                f"Expected '{iid}' to be invalid"
            )

    def test_iso8601_datetime_valid(self) -> None:
        """Test valid ISO 8601 datetime formats."""
        valid_dates = [
            "2026-01-15T09:30:00Z",
            "2026-01-15T09:30:00+00:00",
            "2026-01-15T09:30:00+03:00",
            "2026-01-15T09:30:00-05:00",
            "2026-01-15",
        ]
        for vdate in valid_dates:
            self.assertTrue(
                MODULE.validate_iso8601_datetime(vdate),
                f"Expected '{vdate}' to be valid ISO 8601"
            )

    def test_iso8601_datetime_invalid(self) -> None:
        """Test invalid ISO 8601 datetime formats."""
        invalid_dates = [
            "2026/01/15",
            "15-01-2026",
            "not-a-date",
            "2026-13-01",
            "",
        ]
        for idate in invalid_dates:
            self.assertFalse(
                MODULE.validate_iso8601_datetime(idate),
                f"Expected '{idate}' to be invalid"
            )

    def test_uri_validation_valid(self) -> None:
        """Test valid URIs."""
        valid_uris = [
            "https://example.com",
            "http://example.com/path",
            "https://example.com/path?query=value",
            "https://example.com/path#anchor",
            "https://sub.example.co.uk/path",
        ]
        for vuri in valid_uris:
            self.assertTrue(
                MODULE.validate_uri(vuri),
                f"Expected '{vuri}' to be valid URI"
            )

    def test_uri_validation_invalid(self) -> None:
        """Test invalid URIs."""
        invalid_uris = [
            "not a uri",
            "ftp://example.com",
            "/relative/path",
            "example.com",
            "",
            "ht!tp://example.com",
        ]
        for iuri in invalid_uris:
            self.assertFalse(
                MODULE.validate_uri(iuri),
                f"Expected '{iuri}' to be invalid URI"
            )

    def test_language_code_validation_valid(self) -> None:
        """Test valid ISO 639-1 language codes."""
        valid_codes = [
            "ar",
            "en",
            "fr",
            "ar-SA",
            "en-US",
            "pt-BR",
        ]
        for vcode in valid_codes:
            self.assertTrue(
                MODULE.validate_language_code(vcode),
                f"Expected '{vcode}' to be valid language code"
            )

    def test_language_code_validation_invalid(self) -> None:
        """Test invalid language codes."""
        invalid_codes = [
            "arabic",
            "eng",
            "AR",
            "ar-sa",
            "ar-USA",
            "",
        ]
        for icode in invalid_codes:
            self.assertFalse(
                MODULE.validate_language_code(icode),
                f"Expected '{icode}' to be invalid language code"
            )

    def test_confidence_values(self) -> None:
        """Test confidence value set."""
        expected = {"high", "medium", "low", "unverified"}
        self.assertEqual(MODULE.CONFIDENCE_VALUES, expected)

    def test_claim_types(self) -> None:
        """Test claim type enumeration."""
        expected = {"verified-fact", "estimate", "inference", "third-party-claim"}
        self.assertEqual(MODULE.CLAIM_TYPES, expected)

    def test_reliability_values(self) -> None:
        """Test reliability value set."""
        expected = {"primary", "secondary", "tertiary", "unverified"}
        self.assertEqual(MODULE.RELIABILITY_VALUES, expected)

    def test_entity_types(self) -> None:
        """Test entity type enumeration."""
        expected = {"person", "organization", "company", "government", "location", "project", "other"}
        self.assertEqual(MODULE.ENTITY_TYPES, expected)

    def test_entity_statuses(self) -> None:
        """Test entity status enumeration."""
        expected = {"active", "inactive", "unknown"}
        self.assertEqual(MODULE.ENTITY_STATUSES, expected)


if __name__ == "__main__":
    unittest.main()
