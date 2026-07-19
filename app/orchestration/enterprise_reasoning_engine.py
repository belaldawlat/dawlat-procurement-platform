"""Explainable reasoning for the enterprise decision brain."""

from __future__ import annotations

from app.orchestration.enterprise_decision_models import (
    EnterpriseDecisionDomain,
    EnterpriseDecisionFactor,
    EnterpriseDecisionFinding,
    EnterpriseDecisionSeverity,
)
from app.orchestration.enterprise_decision_policy import (
    EnterpriseDecisionPolicy,
)


class EnterpriseReasoningEngine:
    """Convert decision factors into explainable findings."""

    def reason(
        self,
        factors: tuple[EnterpriseDecisionFactor, ...],
        policy: EnterpriseDecisionPolicy,
    ) -> tuple[EnterpriseDecisionFinding, ...]:
        findings: list[EnterpriseDecisionFinding] = []

        for factor in factors:
            effective_score = factor.effective_score

            if factor.blocking:
                findings.append(
                    EnterpriseDecisionFinding(
                        code=f"BLOCKING_{factor.factor_id.upper()}",
                        message=(
                            factor.explanation
                            or f"{factor.name} is a blocking factor."
                        ),
                        domain=factor.domain,
                        severity=EnterpriseDecisionSeverity.CRITICAL,
                        blocking=True,
                        metadata={
                            "effective_score": effective_score,
                        },
                    )
                )
                continue

            if effective_score <= policy.reject_threshold:
                findings.append(
                    EnterpriseDecisionFinding(
                        code=f"CRITICAL_{factor.factor_id.upper()}",
                        message=(
                            factor.explanation
                            or f"{factor.name} is critically weak."
                        ),
                        domain=factor.domain,
                        severity=EnterpriseDecisionSeverity.CRITICAL,
                        blocking=True,
                        metadata={
                            "effective_score": effective_score,
                        },
                    )
                )
            elif effective_score < policy.hold_threshold:
                findings.append(
                    EnterpriseDecisionFinding(
                        code=f"HIGH_{factor.factor_id.upper()}",
                        message=(
                            factor.explanation
                            or f"{factor.name} requires investigation."
                        ),
                        domain=factor.domain,
                        severity=EnterpriseDecisionSeverity.HIGH,
                        blocking=False,
                        metadata={
                            "effective_score": effective_score,
                        },
                    )
                )
            elif effective_score < policy.proceed_threshold:
                findings.append(
                    EnterpriseDecisionFinding(
                        code=f"MEDIUM_{factor.factor_id.upper()}",
                        message=(
                            factor.explanation
                            or f"{factor.name} requires monitoring."
                        ),
                        domain=factor.domain,
                        severity=EnterpriseDecisionSeverity.MEDIUM,
                        blocking=False,
                        metadata={
                            "effective_score": effective_score,
                        },
                    )
                )
            else:
                findings.append(
                    EnterpriseDecisionFinding(
                        code=f"POSITIVE_{factor.factor_id.upper()}",
                        message=(
                            factor.explanation
                            or f"{factor.name} supports proceeding."
                        ),
                        domain=factor.domain,
                        severity=EnterpriseDecisionSeverity.LOW,
                        blocking=False,
                        metadata={
                            "effective_score": effective_score,
                        },
                    )
                )

        if not findings:
            findings.append(
                EnterpriseDecisionFinding(
                    code="BALANCED_DECISION",
                    message=(
                        "No material decision exceptions were detected."
                    ),
                    domain=EnterpriseDecisionDomain.PROCUREMENT,
                    severity=EnterpriseDecisionSeverity.LOW,
                )
            )

        severity_rank = {
            EnterpriseDecisionSeverity.CRITICAL: 0,
            EnterpriseDecisionSeverity.HIGH: 1,
            EnterpriseDecisionSeverity.MEDIUM: 2,
            EnterpriseDecisionSeverity.LOW: 3,
        }

        return tuple(
            sorted(
                findings,
                key=lambda finding: (
                    severity_rank[finding.severity],
                    not finding.blocking,
                    finding.domain.value,
                    finding.code,
                ),
            )
        )