"""Confidence scoring for Package T enterprise decision intelligence."""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt

from app.orchestration.enterprise_decision_models import (
    EnterpriseDecisionContext,
    EnterpriseDecisionEvidence,
)
from app.orchestration.enterprise_decision_policy import (
    EnterpriseDecisionEnginePolicy,
)


@dataclass(frozen=True)
class EnterpriseDecisionConfidenceResult:
    """Detailed confidence calculation output."""

    confidence: float
    evidence_count: int
    distinct_source_count: int
    average_evidence_confidence: float
    score_dispersion: float
    source_coverage_factor: float
    blocking_evidence_count: int

    def __post_init__(self) -> None:
        for field_name, value in {
            "confidence": self.confidence,
            "average_evidence_confidence": self.average_evidence_confidence,
            "score_dispersion": self.score_dispersion,
            "source_coverage_factor": self.source_coverage_factor,
        }.items():
            if not 0 <= value <= 100:
                raise ValueError(
                    f"{field_name} must be between 0 and 100."
                )

        if self.evidence_count < 0:
            raise ValueError("Evidence count cannot be negative.")
        if self.distinct_source_count < 0:
            raise ValueError("Distinct source count cannot be negative.")
        if self.blocking_evidence_count < 0:
            raise ValueError(
                "Blocking evidence count cannot be negative."
            )

    def as_dict(self) -> dict[str, object]:
        """Return a serialisable confidence payload."""

        return {
            "confidence": self.confidence,
            "evidence_count": self.evidence_count,
            "distinct_source_count": self.distinct_source_count,
            "average_evidence_confidence": (
                self.average_evidence_confidence
            ),
            "score_dispersion": self.score_dispersion,
            "source_coverage_factor": self.source_coverage_factor,
            "blocking_evidence_count": (
                self.blocking_evidence_count
            ),
        }


class EnterpriseDecisionConfidence:
    """Calculate deterministic confidence across cross-module evidence."""

    def calculate(
        self,
        context: EnterpriseDecisionContext,
        policy: EnterpriseDecisionEnginePolicy,
    ) -> EnterpriseDecisionConfidenceResult:
        """Calculate confidence from agreement, source coverage and evidence quality."""

        if not isinstance(context, EnterpriseDecisionContext):
            raise TypeError(
                "Confidence calculation requires an "
                "EnterpriseDecisionContext."
            )

        evidences = tuple(context.evidences)

        if not evidences:
            raise ValueError(
                "At least one evidence item is required."
            )

        average_confidence = round(
            sum(item.confidence for item in evidences)
            / len(evidences),
            4,
        )

        weighted_mean_score = self._weighted_mean_score(
            evidences
        )
        score_dispersion = self._score_dispersion(
            evidences,
            weighted_mean_score,
        )

        distinct_sources = {
            item.source
            for item in evidences
        }
        source_coverage_factor = min(
            100.0,
            (
                len(distinct_sources)
                / max(policy.minimum_distinct_sources, 1)
            )
            * 100.0,
        )

        agreement_factor = max(
            0.0,
            100.0 - score_dispersion,
        )

        confidence = (
            average_confidence * 0.55
            + agreement_factor * 0.30
            + source_coverage_factor * 0.15
        )

        if (
            policy.require_multi_source_evidence
            and len(distinct_sources)
            < policy.minimum_distinct_sources
        ):
            confidence *= (
                len(distinct_sources)
                / policy.minimum_distinct_sources
            )

        blocking_count = sum(
            1
            for item in evidences
            if item.blocking
        )

        if blocking_count:
            confidence = min(confidence, 50.0)

        return EnterpriseDecisionConfidenceResult(
            confidence=round(
                max(0.0, min(100.0, confidence)),
                2,
            ),
            evidence_count=len(evidences),
            distinct_source_count=len(distinct_sources),
            average_evidence_confidence=round(
                average_confidence,
                2,
            ),
            score_dispersion=round(
                max(0.0, min(100.0, score_dispersion)),
                2,
            ),
            source_coverage_factor=round(
                source_coverage_factor,
                2,
            ),
            blocking_evidence_count=blocking_count,
        )

    @staticmethod
    def _weighted_mean_score(
        evidences: tuple[EnterpriseDecisionEvidence, ...],
    ) -> float:
        total_weight = sum(
            max(item.confidence, 1.0)
            for item in evidences
        )

        return sum(
            item.score * max(item.confidence, 1.0)
            for item in evidences
        ) / total_weight

    @staticmethod
    def _score_dispersion(
        evidences: tuple[EnterpriseDecisionEvidence, ...],
        mean_score: float,
    ) -> float:
        total_weight = sum(
            max(item.confidence, 1.0)
            for item in evidences
        )

        variance = sum(
            max(item.confidence, 1.0)
            * ((item.score - mean_score) ** 2)
            for item in evidences
        ) / total_weight

        return min(100.0, sqrt(variance))