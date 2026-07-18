"""Tests for Phase 20 Package B enterprise observability."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from app.observability.audit_logger import (
    AuditEvent,
    AuditLogger,
    AuditOutcome,
)
from app.observability.log_context import (
    create_request_context,
    get_log_context,
    logging_context,
)
from app.observability.logging_config import (
    StructuredJsonFormatter,
)
from app.observability.performance_logger import (
    PerformanceLogger,
)
from app.observability.redaction import (
    REDACTED_VALUE,
    is_sensitive_key,
    redact_mapping,
    redact_value,
)
from app.observability.security_logger import (
    SecurityEvent,
    SecuritySeverity,
)


def test_sensitive_keys_are_detected() -> None:
    assert is_sensitive_key("password") is True
    assert is_sensitive_key("api_key") is True
    assert is_sensitive_key("customer_name") is False


def test_nested_sensitive_values_are_redacted() -> None:
    values = {
        "username": "belal",
        "password": "private",
        "nested": {
            "access_token": "token-value",
            "safe": "visible",
        },
    }

    result = redact_mapping(values)

    assert result["username"] == "belal"
    assert result["password"] == REDACTED_VALUE
    assert result["nested"]["access_token"] == REDACTED_VALUE
    assert result["nested"]["safe"] == "visible"


def test_sequences_are_redacted_recursively() -> None:
    value = [
        {
            "secret_key": "private",
            "status": "active",
        }
    ]

    result = redact_value(value)

    assert result[0]["secret_key"] == REDACTED_VALUE
    assert result[0]["status"] == "active"


def test_request_context_generates_identifiers() -> None:
    context = create_request_context(
        actor_id="owner-1",
    )

    assert context.request_id
    assert context.correlation_id
    assert context.actor_id == "owner-1"


def test_logging_context_is_restored() -> None:
    original = get_log_context()

    context = create_request_context(
        actor_id="owner-1",
    )

    with logging_context(context):
        assert get_log_context() == context

    assert get_log_context() == original


def test_structured_formatter_outputs_json() -> None:
    formatter = StructuredJsonFormatter()

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Test event",
        args=(),
        exc_info=None,
    )

    output = formatter.format(record)
    payload = json.loads(output)

    assert payload["message"] == "Test event"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "test"


def test_formatter_redacts_sensitive_extras() -> None:
    formatter = StructuredJsonFormatter()

    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="Authentication event",
        args=(),
        exc_info=None,
    )

    record.password = "private"
    record.safe_value = "visible"

    payload = json.loads(formatter.format(record))

    assert payload["data"]["password"] == REDACTED_VALUE
    assert payload["data"]["safe_value"] == "visible"


def test_audit_logger_writes_valid_record(
    tmp_path: Path,
) -> None:
    path = tmp_path / "audit.jsonl"
    logger = AuditLogger(path)

    record = logger.record(
        AuditEvent(
            action="supplier.created",
            resource_type="supplier",
            resource_id="supplier-1",
            outcome=AuditOutcome.SUCCESS,
        )
    )

    assert path.exists()
    assert record["record_hash"]
    assert record["previous_hash"] == ""


def test_audit_chain_verifies(
    tmp_path: Path,
) -> None:
    logger = AuditLogger(tmp_path / "audit.jsonl")

    logger.record(
        AuditEvent(
            action="login",
            resource_type="authentication",
            outcome=AuditOutcome.SUCCESS,
        )
    )

    logger.record(
        AuditEvent(
            action="supplier.updated",
            resource_type="supplier",
            outcome=AuditOutcome.SUCCESS,
        )
    )

    assert logger.verify_integrity() is True


def test_audit_chain_detects_tampering(
    tmp_path: Path,
) -> None:
    path = tmp_path / "audit.jsonl"
    logger = AuditLogger(path)

    logger.record(
        AuditEvent(
            action="login",
            resource_type="authentication",
            outcome=AuditOutcome.SUCCESS,
        )
    )

    contents = path.read_text(encoding="utf-8")
    path.write_text(
        contents.replace("login", "tampered-login"),
        encoding="utf-8",
    )

    assert logger.verify_integrity() is False


def test_audit_logger_redacts_details(
    tmp_path: Path,
) -> None:
    logger = AuditLogger(tmp_path / "audit.jsonl")

    record = logger.record(
        AuditEvent(
            action="credentials.updated",
            resource_type="authentication",
            outcome=AuditOutcome.SUCCESS,
            details={
                "password": "private",
            },
        )
    )

    assert record["details"]["password"] == REDACTED_VALUE


def test_security_event_is_immutable() -> None:
    event = SecurityEvent(
        event_type="login_denied",
        severity=SecuritySeverity.HIGH,
        message="Login denied.",
    )

    assert event.event_type == "login_denied"
    assert event.severity is SecuritySeverity.HIGH


def test_performance_logger_measures_success() -> None:
    logger = PerformanceLogger()

    with logger.measure(
        "test-operation",
        warning_threshold_ms=10_000,
    ):
        result = 1 + 1

    assert result == 2


def test_audit_outcomes_are_stable() -> None:
    assert AuditOutcome.SUCCESS.value == "success"
    assert AuditOutcome.FAILURE.value == "failure"
    assert AuditOutcome.DENIED.value == "denied"
    assert AuditOutcome.ERROR.value == "error"


def test_security_severity_values_are_stable() -> None:
    assert SecuritySeverity.INFORMATIONAL.value == (
        "informational"
    )
    assert SecuritySeverity.CRITICAL.value == "critical"