"""Tests for DOI validation."""

import pytest

from sentinel.validate import ValidationStatus, ValidationResult


class TestValidationStatus:
    """Test validation status enum."""

    def test_status_values(self):
        assert ValidationStatus.PASSED.value == "passed"
        assert ValidationStatus.PAYWALL.value == "paywall"
        assert ValidationStatus.FAILED.value == "failed"
        assert ValidationStatus.TIMEOUT.value == "timeout"
        assert ValidationStatus.SKIPPED.value == "skipped"


class TestValidationResult:
    """Test validation result dataclass."""

    def test_passed_result(self):
        result = ValidationResult(
            doi="10.1002/andp.19053220607",
            status=ValidationStatus.PASSED,
            http_code=200,
        )
        assert result.doi == "10.1002/andp.19053220607"
        assert result.status == ValidationStatus.PASSED
        assert result.http_code == 200

    def test_paywall_result(self):
        result = ValidationResult(
            doi="10.1234/test",
            status=ValidationStatus.PAYWALL,
            http_code=403,
        )
        assert result.status == ValidationStatus.PAYWALL
