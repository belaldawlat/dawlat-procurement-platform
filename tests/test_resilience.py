"""Tests for the enterprise resilience package."""

from __future__ import annotations

from typing import Any

import pytest

from app.resilience import (
    AuthorisationError,
    CircuitBreaker,
    CircuitBreakerPolicy,
    CircuitOpenError,
    CircuitState,
    EnterpriseErrorHandler,
    ErrorCategory,
    FailureDisposition,
    NetworkError,
    RecoveryAction,
    RecoveryExecutor,
    RecoveryFailedError,
    RecoveryPolicy,
    ResilienceContext,
    RetryExecutor,
    RetryExhaustedError,
    RetryPolicy,
    ValidationError,
    create_resilience_context,
    get_resilience_context,
    normalise_exception,
    recover_with_default,
    recover_with_fallback,
    resilience_context,
    safe_execute,
)


def test_platform_error_exposes_safe_payload() -> None:
    """Controlled exceptions must expose safe structured details."""

    error = ValidationError(
        technical_message="Invalid internal supplier identifier.",
        metadata={
            "supplier_id": "SUP-100",
            "password": "secret-value",
        },
    )

    payload = error.safe_payload()

    assert payload["code"] == "DAWLAT_VALIDATION_ERROR"
    assert payload["category"] == ErrorCategory.VALIDATION.value
    assert payload["retryable"] is False
    assert payload["message"] == "The supplied information is invalid."
    assert payload["error_id"]
    assert payload["metadata"]["supplier_id"] == "SUP-100"
    assert payload["metadata"]["password"] != "secret-value"


def test_exception_defaults_match_failure_policy() -> None:
    """Exception subclasses must use their intended dispositions."""

    validation_error = ValidationError("Invalid value.")
    network_error = NetworkError("Network unavailable.")
    authorisation_error = AuthorisationError("Access denied.")

    assert (
        validation_error.disposition
        is FailureDisposition.NON_RETRYABLE
    )
    assert validation_error.retryable is False

    assert (
        network_error.disposition
        is FailureDisposition.RETRYABLE
    )
    assert network_error.retryable is True

    assert (
        authorisation_error.disposition
        is FailureDisposition.FAIL_CLOSED
    )
    assert authorisation_error.retryable is False


@pytest.mark.parametrize(
    ("source_error", "expected_type"),
    [
        (ValueError("bad input"), ValidationError),
        (PermissionError("blocked"), AuthorisationError),
        (ConnectionError("offline"), NetworkError),
    ],
)
def test_normalise_exception_maps_known_errors(
    source_error: Exception,
    expected_type: type[Exception],
) -> None:
    """Common Python exceptions must map to enterprise exceptions."""

    normalised = normalise_exception(source_error)

    assert isinstance(normalised, expected_type)


def test_normalise_exception_preserves_platform_error() -> None:
    """An existing enterprise exception must not be replaced."""

    original = NetworkError("Temporary outage.")

    assert normalise_exception(original) is original


def test_resilience_context_validates_operation_name() -> None:
    """A resilience context requires a valid operation name."""

    with pytest.raises(
        ValueError,
        match="operation name is required",
    ):
        ResilienceContext(operation_name="")


def test_resilience_context_generates_identifiers() -> None:
    """Context creation must generate deterministic correlation data."""

    context = create_resilience_context(
        "supplier-sync",
        request_id="REQ-100",
        actor_id="USER-1",
        dependency_name="supplier-api",
        metadata={"token": "sensitive"},
    )

    assert context.operation_name == "supplier-sync"
    assert context.operation_id
    assert context.request_id == "REQ-100"
    assert context.correlation_id == "REQ-100"
    assert context.actor_id == "USER-1"
    assert context.dependency_name == "supplier-api"
    assert context.metadata["token"] != "sensitive"


def test_resilience_context_next_attempt_preserves_identity() -> None:
    """Retry contexts must preserve operation identity."""

    first = create_resilience_context(
        "quotation-import",
        correlation_id="CORR-1",
    )
    second = first.next_attempt()

    assert second.operation_id == first.operation_id
    assert second.correlation_id == first.correlation_id
    assert second.operation_name == first.operation_name
    assert second.attempt_number == 2


def test_resilience_context_manager_restores_previous_context() -> None:
    """Context activation must be safely scoped."""

    previous = get_resilience_context()
    active = create_resilience_context("shipment-create")

    with resilience_context(active):
        assert get_resilience_context() is active

    assert get_resilience_context() is previous


def test_retry_policy_calculates_bounded_backoff() -> None:
    """Retry delay must grow exponentially and remain bounded."""

    policy = RetryPolicy(
        max_attempts=5,
        initial_delay_seconds=1.0,
        maximum_delay_seconds=3.0,
        backoff_multiplier=2.0,
        jitter_ratio=0.0,
    )

    assert policy.delay_for_attempt(1) == 1.0
    assert policy.delay_for_attempt(2) == 2.0
    assert policy.delay_for_attempt(3) == 3.0
    assert policy.delay_for_attempt(4) == 3.0


def test_retry_policy_rejects_invalid_configuration() -> None:
    """Unsafe retry configuration must fail immediately."""

    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=0)

    with pytest.raises(ValueError):
        RetryPolicy(
            initial_delay_seconds=2.0,
            maximum_delay_seconds=1.0,
        )

    with pytest.raises(ValueError):
        RetryPolicy(jitter_ratio=1.5)


def test_retry_executor_returns_after_retryable_failure() -> None:
    """Retryable failures must be retried until success."""

    state = {"attempts": 0}
    sleep_calls: list[float] = []

    def operation() -> str:
        state["attempts"] += 1

        if state["attempts"] < 3:
            raise NetworkError("Temporary network failure.")

        return "completed"

    executor = RetryExecutor(
        RetryPolicy(
            max_attempts=3,
            initial_delay_seconds=0.1,
            maximum_delay_seconds=1.0,
            jitter_ratio=0.0,
        ),
        sleep_function=sleep_calls.append,
    )

    result = executor.execute(
        operation,
        operation_name="supplier-discovery",
    )

    assert result.value == "completed"
    assert state["attempts"] == 3
    assert len(result.attempts) == 3
    assert result.attempts[0].successful is False
    assert result.attempts[1].successful is False
    assert result.attempts[2].successful is True
    assert sleep_calls == [0.1, 0.2]


def test_retry_executor_does_not_retry_non_retryable_error() -> None:
    """Validation failures must not be retried."""

    state = {"attempts": 0}

    def operation() -> None:
        state["attempts"] += 1
        raise ValidationError("Invalid quotation.")

    executor = RetryExecutor(
        RetryPolicy(max_attempts=4),
        sleep_function=lambda _: None,
    )

    with pytest.raises(ValidationError):
        executor.execute(
            operation,
            operation_name="quotation-validation",
        )

    assert state["attempts"] == 1


def test_retry_executor_raises_when_attempts_exhausted() -> None:
    """Exhausted retryable operations must raise a stable error."""

    state = {"attempts": 0}

    def operation() -> None:
        state["attempts"] += 1
        raise NetworkError("Still unavailable.")

    executor = RetryExecutor(
        RetryPolicy(
            max_attempts=3,
            initial_delay_seconds=0,
            maximum_delay_seconds=0,
            jitter_ratio=0,
        ),
        sleep_function=lambda _: None,
    )

    with pytest.raises(RetryExhaustedError) as captured:
        executor.execute(
            operation,
            operation_name="freight-api",
        )

    assert state["attempts"] == 3
    assert captured.value.code == "DAWLAT_RETRY_EXHAUSTED"


def test_circuit_breaker_opens_after_failure_threshold() -> None:
    """Repeated retryable failures must open the circuit."""

    breaker: CircuitBreaker[str] = CircuitBreaker(
        "supplier-api",
        CircuitBreakerPolicy(
            failure_threshold=2,
            recovery_timeout_seconds=60,
        ),
    )

    def failing_operation() -> str:
        raise NetworkError("Supplier API unavailable.")

    with pytest.raises(NetworkError):
        breaker.execute(failing_operation)

    assert breaker.snapshot().state is CircuitState.CLOSED
    assert breaker.snapshot().failure_count == 1

    with pytest.raises(NetworkError):
        breaker.execute(failing_operation)

    snapshot = breaker.snapshot()

    assert snapshot.state is CircuitState.OPEN
    assert snapshot.failure_count == 2
    assert breaker.allow_request() is False

    with pytest.raises(CircuitOpenError):
        breaker.execute(lambda: "blocked")


def test_circuit_breaker_recovers_through_half_open() -> None:
    """An open circuit must recover after a successful probe."""

    clock_value = {"time": 100.0}

    def clock() -> float:
        return clock_value["time"]

    breaker: CircuitBreaker[str] = CircuitBreaker(
        "freight-service",
        CircuitBreakerPolicy(
            failure_threshold=1,
            recovery_timeout_seconds=10,
            half_open_success_threshold=1,
        ),
        clock=clock,
    )

    with pytest.raises(NetworkError):
        breaker.execute(
            lambda: (_ for _ in ()).throw(
                NetworkError("Freight service failed.")
            )
        )

    assert breaker.snapshot().state is CircuitState.OPEN

    clock_value["time"] = 111.0

    assert breaker.snapshot().state is CircuitState.HALF_OPEN
    assert breaker.allow_request() is True
    assert breaker.execute(lambda: "recovered") == "recovered"
    assert breaker.snapshot().state is CircuitState.CLOSED


def test_circuit_breaker_ignores_validation_failures() -> None:
    """Client validation errors must not damage dependency health."""

    breaker: CircuitBreaker[None] = CircuitBreaker(
        "quotation-service",
        CircuitBreakerPolicy(failure_threshold=1),
    )

    with pytest.raises(ValidationError):
        breaker.execute(
            lambda: (_ for _ in ()).throw(
                ValidationError("Invalid quotation.")
            )
        )

    snapshot = breaker.snapshot()

    assert snapshot.state is CircuitState.CLOSED
    assert snapshot.failure_count == 0


def test_circuit_breaker_manual_controls() -> None:
    """Manual open and reset operations must be deterministic."""

    breaker: CircuitBreaker[str] = CircuitBreaker(
        "payment-service"
    )

    breaker.force_open()

    assert breaker.snapshot().state is CircuitState.OPEN

    breaker.reset()

    snapshot = breaker.snapshot()

    assert snapshot.state is CircuitState.CLOSED
    assert snapshot.failure_count == 0


def test_recovery_executor_uses_fallback() -> None:
    """Fallback recovery must return a structured result."""

    executor = RecoveryExecutor(
        RecoveryPolicy(
            action=RecoveryAction.FALLBACK,
        )
    )

    result = executor.execute(
        lambda: (_ for _ in ()).throw(
            NetworkError("Primary dependency failed.")
        ),
        operation_name="supplier-search",
        fallback=lambda error: f"fallback:{error.code}",
    )

    assert result.recovered is True
    assert result.action is RecoveryAction.FALLBACK
    assert result.value == "fallback:DAWLAT_NETWORK_ERROR"
    assert result.original_error_code == "DAWLAT_NETWORK_ERROR"
    assert result.original_error_id


def test_recovery_executor_returns_default_value() -> None:
    """Default recovery must return the configured value."""

    result = recover_with_default(
        lambda: (_ for _ in ()).throw(
            NetworkError("Inventory API unavailable.")
        ),
        operation_name="inventory-summary",
        default_value={"available": 0},
    )

    assert result.recovered is True
    assert result.action is RecoveryAction.DEFAULT_VALUE
    assert result.value == {"available": 0}


def test_recovery_executor_reraises_disallowed_error() -> None:
    """Recovery must not bypass fail-closed security errors."""

    executor = RecoveryExecutor(
        RecoveryPolicy(
            action=RecoveryAction.DEFAULT_VALUE,
        )
    )

    with pytest.raises(AuthorisationError):
        executor.execute(
            lambda: (_ for _ in ()).throw(
                AuthorisationError("Unauthorised access.")
            ),
            operation_name="financial-command-centre",
            default_value={},
        )


def test_recovery_executor_requires_fallback_function() -> None:
    """Fallback action without a function must fail safely."""

    executor = RecoveryExecutor(
        RecoveryPolicy(
            action=RecoveryAction.FALLBACK,
        )
    )

    with pytest.raises(RecoveryFailedError):
        executor.execute(
            lambda: (_ for _ in ()).throw(
                NetworkError("Dependency unavailable.")
            ),
            operation_name="market-data",
        )


def test_recovery_executor_wraps_fallback_failure() -> None:
    """A failed fallback must become a recovery failure."""

    def broken_fallback(_: Exception) -> str:
        raise RuntimeError("Fallback storage unavailable.")

    with pytest.raises(RecoveryFailedError):
        recover_with_fallback(
            lambda: (_ for _ in ()).throw(
                NetworkError("Primary storage unavailable.")
            ),
            operation_name="document-storage",
            fallback=broken_fallback,
        )


def test_error_handler_returns_safe_response() -> None:
    """The central handler must return safe external information."""

    handler = EnterpriseErrorHandler()
    context = create_resilience_context(
        "shipment-update",
        correlation_id="CORR-500",
    )

    result = handler.handle(
        NetworkError(
            "Internal host 10.1.1.5 was unreachable.",
            metadata={"api_key": "private-key"},
        ),
        context=context,
    )

    response = result.response.as_dict()

    assert response["success"] is False
    assert response["error"]["code"] == "DAWLAT_NETWORK_ERROR"
    assert (
        response["error"]["message"]
        == "The network operation could not be completed."
    )
    assert (
        response["error"]["metadata"]["correlation_id"]
        == "CORR-500"
    )
    assert result.should_retry is True
    assert result.should_alert is False
    assert result.should_fail_closed is False


def test_error_handler_classifies_high_severity_error() -> None:
    """High-severity failures must trigger alert classification."""

    handler = EnterpriseErrorHandler()

    result = handler.handle(
        AuthorisationError("Blocked operation."),
        operation_name="user-management",
    )

    assert result.should_alert is True
    assert result.should_retry is False
    assert result.should_fail_closed is True


def test_error_handler_execute_returns_operation_value() -> None:
    """Successful operations must pass through unchanged."""

    handler = EnterpriseErrorHandler()

    result = handler.execute(
        lambda: {"status": "ok"},
        operation_name="health-check",
    )

    assert result == {"status": "ok"}


def test_safe_execute_converts_failure_to_error_response() -> None:
    """Shared safe execution must never expose raw exceptions."""

    result = safe_execute(
        lambda: (_ for _ in ()).throw(
            ValueError("Sensitive invalid value.")
        ),
        operation_name="supplier-create",
    )

    assert hasattr(result, "as_dict")

    payload = result.as_dict()  # type: ignore[union-attr]

    assert payload["success"] is False
    assert payload["error"]["code"] == "DAWLAT_VALIDATION_ERROR"
    assert (
        payload["error"]["message"]
        == "The supplied information is invalid."
    )


def test_resilience_public_api_is_importable() -> None:
    """Package exports must remain stable for platform modules."""

    imported_values: dict[str, Any] = {
        "CircuitBreaker": CircuitBreaker,
        "RetryExecutor": RetryExecutor,
        "RecoveryExecutor": RecoveryExecutor,
        "EnterpriseErrorHandler": EnterpriseErrorHandler,
        "ResilienceContext": ResilienceContext,
    }

    assert all(
        value is not None
        for value in imported_values.values()
    )