"""
Supplier Ranking Engine.

This module evaluates and ranks live global search results for procurement use.
It does not treat search results as verified suppliers. It assigns transparent
scores based on relevance, company type, evidence quality, country match,
official-domain signals, certificate signals, contact signals and risk flags.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable
from urllib.parse import urlparse

from services.global_search_provider import SearchResult


LOW_TRUST_DOMAINS = {
    "facebook.com",
    "www.facebook.com",
    "instagram.com",
    "www.instagram.com",
    "linkedin.com",
    "www.linkedin.com",
    "youtube.com",
    "www.youtube.com",
    "alibaba.com",
    "www.alibaba.com",
    "made-in-china.com",
    "www.made-in-china.com",
}

DIRECTORY_SIGNALS = {
    "directory",
    "yellow pages",
    "marketplace",
    "listing",
    "supplier list",
    "trade portal",
}

MANUFACTURER_SIGNALS = {
    "manufacturer",
    "factory",
    "producer",
    "mill",
    "processing plant",
    "production",
}

EXPORTER_SIGNALS = {
    "exporter",
    "export",
    "international markets",
    "global markets",
    "overseas",
}

CONTACT_SIGNALS = {
    "contact",
    "email",
    "phone",
    "whatsapp",
    "zalo",
    "address",
}

CERTIFICATE_SIGNALS = {
    "iso",
    "haccp",
    "halal",
    "brc",
    "brcgs",
    "gmp",
    "fda",
    "ce",
    "globalgap",
    "organic",
    "sgs",
    "bureau veritas",
    "phytosanitary",
}

PROCUREMENT_SIGNALS = {
    "moq",
    "incoterm",
    "fob",
    "cif",
    "exw",
    "quotation",
    "price",
    "lead time",
    "payment terms",
    "private label",
    "packaging",
}


@dataclass
class RankedSupplierResult:
    title: str
    url: str
    source_name: str
    snippet: str

    overall_score: int
    country_score: int
    company_type_score: int
    evidence_score: int
    procurement_score: int
    contact_score: int

    classification: str
    recommendation: str
    risk_flags: list[str] = field(default_factory=list)
    matched_signals: list[str] = field(default_factory=list)


class SupplierRankingEngine:
    """Rank live search results for supplier-discovery workflows."""

    def rank(
        self,
        results: Iterable[SearchResult],
        *,
        product: str,
        country: str = "",
        partner_type: str = "Supplier",
    ) -> list[RankedSupplierResult]:
        ranked = [
            self._evaluate(
                result,
                product=product,
                country=country,
                partner_type=partner_type,
            )
            for result in results
        ]

        ranked.sort(
            key=lambda item: (
                item.overall_score,
                -len(item.risk_flags),
                item.evidence_score,
            ),
            reverse=True,
        )
        return ranked

    def _evaluate(
        self,
        result: SearchResult,
        *,
        product: str,
        country: str,
        partner_type: str,
    ) -> RankedSupplierResult:
        text = " ".join(
            [
                result.title or "",
                result.snippet or "",
                result.source_name or "",
                result.url or "",
            ]
        ).lower()

        domain = self._domain(result.url)
        risk_flags: list[str] = []
        matched_signals: list[str] = []

        product_score = self._term_score(
            text,
            self._tokens(product),
            maximum=25,
        )

        country_score = self._country_score(
            text=text,
            domain=domain,
            country=country,
        )

        company_type_score, classification, company_matches = (
            self._company_type_score(
                text=text,
                partner_type=partner_type,
            )
        )
        matched_signals.extend(company_matches)

        evidence_score = 0
        if domain and domain not in LOW_TRUST_DOMAINS:
            evidence_score += 12
            matched_signals.append("Independent company domain")

        if result.snippet and len(result.snippet.strip()) >= 120:
            evidence_score += 6
            matched_signals.append("Detailed source summary")

        if result.metadata.get("relevance_score") is not None:
            relevance = float(result.metadata["relevance_score"] or 0)
            evidence_score += min(7, round(relevance * 7))

        contact_matches = self._matches(text, CONTACT_SIGNALS)
        contact_score = min(10, len(contact_matches) * 3)
        matched_signals.extend(contact_matches)

        certificate_matches = self._matches(
            text,
            CERTIFICATE_SIGNALS,
        )
        evidence_score += min(12, len(certificate_matches) * 4)
        matched_signals.extend(certificate_matches)

        procurement_matches = self._matches(
            text,
            PROCUREMENT_SIGNALS,
        )
        procurement_score = min(
            16,
            len(procurement_matches) * 3,
        )
        matched_signals.extend(procurement_matches)

        if domain in LOW_TRUST_DOMAINS:
            risk_flags.append(
                "Social media or marketplace result; not an official company website"
            )

        if self._matches(text, DIRECTORY_SIGNALS):
            risk_flags.append(
                "Directory or listing result; company identity requires separate verification"
            )

        if country.strip() and country.lower() not in text:
            risk_flags.append(
                f"Requested country '{country}' is not clearly confirmed"
            )

        if not certificate_matches:
            risk_flags.append("No certificate evidence found in result")

        if not contact_matches:
            risk_flags.append("No business contact evidence found in result")

        raw_score = (
            product_score
            + country_score
            + company_type_score
            + evidence_score
            + procurement_score
            + contact_score
        )

        penalty = min(30, len(risk_flags) * 6)
        overall_score = max(0, min(100, raw_score - penalty))

        if overall_score >= 80 and not risk_flags:
            recommendation = "High-priority candidate"
        elif overall_score >= 65:
            recommendation = "Review and verify"
        elif overall_score >= 45:
            recommendation = "Secondary research candidate"
        else:
            recommendation = "Low relevance or high uncertainty"

        return RankedSupplierResult(
            title=result.title,
            url=result.url,
            source_name=result.source_name,
            snippet=result.snippet,
            overall_score=overall_score,
            country_score=country_score,
            company_type_score=company_type_score,
            evidence_score=min(30, evidence_score),
            procurement_score=procurement_score,
            contact_score=contact_score,
            classification=classification,
            recommendation=recommendation,
            risk_flags=list(dict.fromkeys(risk_flags)),
            matched_signals=list(dict.fromkeys(matched_signals)),
        )

    def _country_score(
        self,
        *,
        text: str,
        domain: str,
        country: str,
    ) -> int:
        if not country.strip():
            return 10

        country_name = country.lower().strip()
        score = 0

        if country_name in text:
            score += 15

        country_domain_hints = {
            "vietnam": ".vn",
            "india": ".in",
            "pakistan": ".pk",
            "china": ".cn",
            "australia": ".au",
            "thailand": ".th",
        }

        suffix = country_domain_hints.get(country_name)

        if suffix and domain.endswith(suffix):
            score += 10

        return min(25, score)

    def _company_type_score(
        self,
        *,
        text: str,
        partner_type: str,
    ) -> tuple[int, str, list[str]]:
        manufacturer_matches = self._matches(
            text,
            MANUFACTURER_SIGNALS,
        )
        exporter_matches = self._matches(
            text,
            EXPORTER_SIGNALS,
        )

        score = 0
        classification = "Unclassified"

        if manufacturer_matches:
            score += min(20, len(manufacturer_matches) * 6)
            classification = "Manufacturer"

        if exporter_matches:
            score += min(12, len(exporter_matches) * 4)
            classification = (
                "Manufacturer & Exporter"
                if manufacturer_matches
                else "Exporter"
            )

        if not manufacturer_matches and not exporter_matches:
            if "distributor" in text or "wholesale" in text:
                classification = "Distributor / Wholesaler"
                score += 4
            elif self._matches(text, DIRECTORY_SIGNALS):
                classification = "Directory / Marketplace"
            else:
                classification = partner_type

        return (
            min(30, score),
            classification,
            manufacturer_matches + exporter_matches,
        )

    @staticmethod
    def _term_score(
        text: str,
        terms: list[str],
        *,
        maximum: int,
    ) -> int:
        if not terms:
            return 0

        matches = sum(1 for term in terms if term in text)
        return min(maximum, round(maximum * matches / len(terms)))

    @staticmethod
    def _matches(
        text: str,
        signals: Iterable[str],
    ) -> list[str]:
        return [
            signal
            for signal in signals
            if signal in text
        ]

    @staticmethod
    def _tokens(value: str) -> list[str]:
        return [
            token.lower()
            for token in value.replace("-", " ").split()
            if len(token.strip()) >= 2
        ]

    @staticmethod
    def _domain(url: str) -> str:
        try:
            return urlparse(url).netloc.lower()
        except ValueError:
            return ""


_engine = SupplierRankingEngine()


def rank_supplier_results(
    results: Iterable[SearchResult],
    *,
    product: str,
    country: str = "",
    partner_type: str = "Supplier",
) -> list[RankedSupplierResult]:
    """Public ranking function used by Global Discovery."""

    return _engine.rank(
        results,
        product=product,
        country=country,
        partner_type=partner_type,
    )