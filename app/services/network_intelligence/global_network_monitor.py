"""Global Network Monitor for GPNI.

Evaluates active procurement network cases for urgent commercial, payment,
contract, supplier, buyer, logistics and compliance conditions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Iterable


class NetworkAlertSeverity(str, Enum):
    INFO = "Info"
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"
    CRITICAL = "Critical"


@dataclass(frozen=True)
class NetworkAlert:
    alert_id: str
    case_id: str
    category: str
    severity: NetworkAlertSeverity
    title: str
    description: str
    owner_role: str
    action_required: str
    blocking: bool
    evidence: tuple[str, ...] = ()
    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat(
            timespec="seconds"
        )
    )


@dataclass(frozen=True)
class NetworkHealthSummary:
    total_cases: int
    healthy_cases: int
    warning_cases: int
    blocked_cases: int
    critical_alerts: int
    high_alerts: int
    alerts: tuple[NetworkAlert, ...]
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(
            timespec="seconds"
        )
    )


class GlobalNetworkMonitor:
    """Continuously evaluate GPNI cases for material change."""

    def monitor(
        self,
        cases: Iterable[dict[str, Any]],
    ) -> NetworkHealthSummary:
        alerts: list[NetworkAlert] = []
        total_cases = 0
        healthy_cases = 0
        warning_cases = 0
        blocked_cases = 0

        for case in cases:
            total_cases += 1
            case_alerts = self._evaluate_case(case)
            alerts.extend(case_alerts)

            if any(alert.blocking for alert in case_alerts):
                blocked_cases += 1
            elif case_alerts:
                warning_cases += 1
            else:
                healthy_cases += 1

        alerts.sort(
            key=lambda alert: (
                -self._severity_rank(alert.severity),
                alert.case_id,
                alert.category,
            )
        )

        return NetworkHealthSummary(
            total_cases=total_cases,
            healthy_cases=healthy_cases,
            warning_cases=warning_cases,
            blocked_cases=blocked_cases,
            critical_alerts=sum(
                1
                for alert in alerts
                if alert.severity
                == NetworkAlertSeverity.CRITICAL
            ),
            high_alerts=sum(
                1
                for alert in alerts
                if alert.severity
                == NetworkAlertSeverity.HIGH
            ),
            alerts=tuple(alerts),
        )

    def _evaluate_case(
        self,
        case: dict[str, Any],
    ) -> list[NetworkAlert]:
        case_id = str(
            case.get("case_id")
            or case.get("id")
            or "UNKNOWN"
        )
        alerts: list[NetworkAlert] = []

        if not case.get("buyer_verified"):
            alerts.append(
                self._alert(
                    case_id,
                    category="Buyer",
                    severity=NetworkAlertSeverity.HIGH,
                    title="Buyer verification incomplete",
                    description=(
                        "Buyer identity or authority is not fully verified."
                    ),
                    owner_role="Customer Acquisition Manager",
                    action_required=(
                        "Complete buyer verification before progressing."
                    ),
                    blocking=True,
                )
            )

        if not case.get("supplier_verified"):
            alerts.append(
                self._alert(
                    case_id,
                    category="Supplier",
                    severity=NetworkAlertSeverity.HIGH,
                    title="Supplier verification incomplete",
                    description=(
                        "Supplier identity, capacity or export readiness is incomplete."
                    ),
                    owner_role="Global Sourcing Specialist",
                    action_required=(
                        "Complete supplier qualification before quotation commitment."
                    ),
                    blocking=True,
                )
            )

        margin = _number(
            case.get("margin_percent")
        )
        minimum_margin = _number(
            case.get("minimum_margin_percent")
            or 15
        )

        if margin and margin < minimum_margin:
            alerts.append(
                self._alert(
                    case_id,
                    category="Commercial",
                    severity=NetworkAlertSeverity.CRITICAL,
                    title="Protected margin breached",
                    description=(
                        f"Projected margin {margin:.2f}% is below "
                        f"the protected minimum {minimum_margin:.2f}%."
                    ),
                    owner_role="Commercial Manager",
                    action_required=(
                        "Renegotiate price, landed cost or sale terms."
                    ),
                    blocking=True,
                )
            )

        if (
            _number(case.get("supplier_commitment"))
            > _number(case.get("cleared_buyer_funds"))
        ):
            alerts.append(
                self._alert(
                    case_id,
                    category="Payment",
                    severity=NetworkAlertSeverity.CRITICAL,
                    title="Supplier commitment exceeds cleared funds",
                    description=(
                        "The proposed supplier commitment is greater than "
                        "verified cleared buyer funds."
                    ),
                    owner_role="Finance Approver",
                    action_required=(
                        "Block payment and obtain additional cleared funds."
                    ),
                    blocking=True,
                )
            )

        if case.get("compliance_hold"):
            alerts.append(
                self._alert(
                    case_id,
                    category="Compliance",
                    severity=NetworkAlertSeverity.CRITICAL,
                    title="Compliance hold active",
                    description=(
                        "A sanctions, regulatory or document hold is active."
                    ),
                    owner_role="Compliance Manager",
                    action_required=(
                        "Resolve the compliance hold before any binding action."
                    ),
                    blocking=True,
                )
            )

        expiry = _parse_date(
            case.get("quotation_expiry")
        )

        if expiry is not None:
            days_remaining = (
                expiry - date.today()
            ).days

            if days_remaining < 0:
                alerts.append(
                    self._alert(
                        case_id,
                        category="Quotation",
                        severity=NetworkAlertSeverity.HIGH,
                        title="Quotation expired",
                        description=(
                            "The current commercial quotation has expired."
                        ),
                        owner_role="Procurement Specialist",
                        action_required=(
                            "Request a refreshed quotation and revalidate terms."
                        ),
                        blocking=True,
                    )
                )
            elif days_remaining <= 3:
                alerts.append(
                    self._alert(
                        case_id,
                        category="Quotation",
                        severity=NetworkAlertSeverity.MEDIUM,
                        title="Quotation expiring soon",
                        description=(
                            f"The quotation expires in {days_remaining} day(s)."
                        ),
                        owner_role="Procurement Specialist",
                        action_required=(
                            "Complete review or request validity extension."
                        ),
                        blocking=False,
                    )
                )

        if case.get("shipment_delayed"):
            alerts.append(
                self._alert(
                    case_id,
                    category="Logistics",
                    severity=NetworkAlertSeverity.HIGH,
                    title="Shipment delay detected",
                    description=str(
                        case.get("delay_reason")
                        or "Shipment delay requires attention."
                    ),
                    owner_role="Logistics Manager",
                    action_required=(
                        "Confirm revised ETA, buyer impact and mitigation plan."
                    ),
                    blocking=bool(
                        case.get("delay_blocks_delivery")
                    ),
                )
            )

        if case.get("relationship_conflict_detected"):
            alerts.append(
                self._alert(
                    case_id,
                    category="Relationship",
                    severity=NetworkAlertSeverity.HIGH,
                    title="Commercial relationship conflict",
                    description=(
                        "A protected buyer or supplier relationship conflict "
                        "has been detected."
                    ),
                    owner_role="Managing Director",
                    action_required=(
                        "Review confidentiality, channel ownership and contact restrictions."
                    ),
                    blocking=True,
                )
            )

        return alerts

    @staticmethod
    def _alert(
        case_id: str,
        *,
        category: str,
        severity: NetworkAlertSeverity,
        title: str,
        description: str,
        owner_role: str,
        action_required: str,
        blocking: bool,
        evidence: tuple[str, ...] = (),
    ) -> NetworkAlert:
        alert_id = (
            f"NET-{case_id}-{category}-"
            f"{abs(hash((title, description))) % 1000000:06d}"
        )

        return NetworkAlert(
            alert_id=alert_id,
            case_id=case_id,
            category=category,
            severity=severity,
            title=title,
            description=description,
            owner_role=owner_role,
            action_required=action_required,
            blocking=blocking,
            evidence=evidence,
        )

    @staticmethod
    def _severity_rank(
        severity: NetworkAlertSeverity,
    ) -> int:
        return {
            NetworkAlertSeverity.CRITICAL: 5,
            NetworkAlertSeverity.HIGH: 4,
            NetworkAlertSeverity.MEDIUM: 3,
            NetworkAlertSeverity.LOW: 2,
            NetworkAlertSeverity.INFO: 1,
        }[severity]


def _number(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _parse_date(value: Any) -> date | None:
    if not value:
        return None

    try:
        return datetime.fromisoformat(
            str(value)[:10]
        ).date()
    except ValueError:
        return None


_monitor = GlobalNetworkMonitor()


def get_global_network_monitor() -> GlobalNetworkMonitor:
    return _monitor