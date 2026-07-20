"""Human-readable explanations for Package T decisions."""

from __future__ import annotations

from dataclasses import dataclass

from app.orchestration.enterprise_decision_confidence import (
    EnterpriseDecisionConfidenceResult,
)
from app.orchestration.enterprise_decision_models import (
    EnterpriseDecisionContext,
    EnterpriseDecisionOutcome,
)
from app.orchestration.enterprise_decision_policy import (
    EnterpriseDecisionEnginePolicy,
)


@dataclass(frozen=True)
class EnterpriseDecisionExplanation:
    """Structured explanation for one enterprise decision."""

    summary: str
    primary_reason: str
    supporting_reasons: tuple[str, ...]
    warnings: tuple[str, ...]
    source_references: tuple[str, ...]

    def __post_init__(self) -> None:
        if not str(self.summary or "").strip():
            raise ValueError("Decision explanation summary is required.")
        if not str(self.primary_reason or "").strip():
            raise ValueError(
                "Decision explanation primary reason is required."
            )

        object.__setattr__(
            self,
            "summary",
            str(self.summary).strip(),
        )
        object.__setattr__(
            self,
            "primary_reason",
            str(self.primary_reason).strip(),
        )
        object.__setattr__(
            self,
            "supporting_reasons",
            tuple(self.supporting_reasons),
        )
        object.__setattr__(
            self,
            "warnings",
            tuple(self.warnings),
        )
        object.__setattr__(
            self,
            "source_references",
            tuple(self.source_references),
        )

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable explanation."""

        return {
            "summary": self.summary,
            "primary_reason": self.primary_reason,
            "supporting_reasons": list(
                self.supporting_reasons
            ),
            "warnings": list(self.warnings),
            "source_references": list(
                self.source_references
            ),
        }


class EnterpriseDecisionExplainer:
    """Generate deterministic and audit-friendly decision explanations."""

    def explain(
        self,
        *,
        context: EnterpriseDecisionContext,
        outcome: EnterpriseDecisionOutcome,
        score: float,
        confidence: EnterpriseDecisionConfidenceResult,
        policy: EnterpriseDecisionEnginePolicy,
    ) -> EnterpriseDecisionExplanation:
        """Explain a unified decision outcome."""

        if not 0 <= score <= 100:
            raise ValueError("Decision score must be between 0 and 100.")

        sorted_evidence = tuple(
            sorted(
                context.evidences,
                key=lambda item: (
                    not item.blocking,
                    -item.confidence,
                    -item.score,
                    item.evidence_id,
                ),
            )
        )

        blocking_evidence = tuple(
            item
            for item in sorted_evidence
            if item.blocking
        )

        if blocking_evidence:
            primary_reason = (
                "Blocking evidence prevents automatic execution: "
                f"{blocking_evidence[0].summary}"
            )
        elif sorted_evidence:
            strongest = sorted_evidence[0]
            primary_reason = (
                f"Strongest evidence from {strongest.source.value}: "
                f"{strongest.summary}"
            )
        else:
            primary_reason = (
                "No evidence was available to support the decision."
            )

        supporting_reasons = tuple(
            (
                f"{item.source.value}: {item.summary} "
                f"(score {item.score:.1f}, "
                f"confidence {item.confidence:.1f})"
            )
            for item in sorted_evidence[:5]
        )

        warnings: list[str] = []

        if (
            confidence.distinct_source_count
            < policy.minimum_distinct_sources
        ):
            warnings.append(
                "Evidence does not meet the configured "
                "multi-source requirement."
            )

        if confidence.confidence < policy.minimum_confidence:
            warnings.append(
                "Decision confidence is below the automatic "
                "execution threshold."
            )

        if blocking_evidence:
            warnings.append(
                "One or more blocking evidence items require "
                "manual review or rejection."
            )

        summary = self._summary_for(
            outcome=outcome,
            score=score,
            confidence=confidence.confidence,
        )

        source_references = tuple(
            sorted(
                {
                    f"{item.source.value}:{item.reference_id}"
                    for item in context.evidences
                }
            )
        )

        return EnterpriseDecisionExplanation(
            summary=summary,
            primary_reason=primary_reason,
            supporting_reasons=supporting_reasons,
            warnings=tuple(warnings),
            source_references=source_references,
        )

    @staticmethod
    def _summary_for(
        *,
        outcome: EnterpriseDecisionOutcome,
        score: float,
        confidence: float,
    ) -> str:
        return (
            f"Decision outcome is {outcome.value} with "
            f"score {score:.2f} and confidence "
            f"{confidence:.2f}."
        )