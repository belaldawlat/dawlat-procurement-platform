"""
Provider-neutral live global search connector.

This module defines the contract used by the Dawlat Procurement Platform
to connect approved live-search providers without coupling the platform
to one API vendor.

The current implementation is intentionally safe:
- no live provider is enabled by default;
- no API key is hard-coded;
- all external results remain unverified;
- provider failures return structured errors;
- the rest of the platform can continue working offline.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class SearchQuery:
    """One global search request."""

    query: str
    country: str = ""
    language: str = "en"
    max_results: int = 10


@dataclass
class SearchResult:
    """One raw external search result."""

    title: str
    url: str
    snippet: str = ""
    source_name: str = ""
    published_at: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchResponse:
    """Structured response returned by every search provider."""

    success: bool
    provider_name: str
    query: SearchQuery
    results: list[SearchResult] = field(default_factory=list)
    error_message: str | None = None
    generated_at: str = field(
        default_factory=lambda: datetime.now().isoformat(
            timespec="seconds"
        )
    )


class GlobalSearchProvider(ABC):
    """Interface implemented by approved live-search adapters."""

    provider_name = "Unknown Provider"

    @abstractmethod
    def search(self, query: SearchQuery) -> SearchResponse:
        """Execute one live global search request."""


class DisabledSearchProvider(GlobalSearchProvider):
    """
    Safe default provider.

    It keeps the platform operational until an approved provider and
    credentials are configured.
    """

    provider_name = "Live Search Not Configured"

    def search(self, query: SearchQuery) -> SearchResponse:
        return SearchResponse(
            success=False,
            provider_name=self.provider_name,
            query=query,
            results=[],
            error_message=(
                "No approved live global search provider is configured. "
                "Configure a provider and API credentials before running "
                "external company research."
            ),
        )


class GlobalSearchGateway:
    """
    Single entry point used by services and UI pages.

    The provider can later be replaced with Bing, Google, SerpAPI,
    Tavily or another approved provider without changing the rest of
    the application.
    """

    def __init__(
        self,
        provider: GlobalSearchProvider | None = None,
    ) -> None:
        self._provider = provider or DisabledSearchProvider()

    @property
    def provider_name(self) -> str:
        return self._provider.provider_name

    def search(
        self,
        query: str,
        *,
        country: str = "",
        language: str = "en",
        max_results: int = 10,
    ) -> SearchResponse:
        cleaned_query = " ".join((query or "").strip().split())

        if not cleaned_query:
            raise ValueError("Search query is required.")

        if max_results < 1 or max_results > 100:
            raise ValueError(
                "max_results must be between 1 and 100."
            )

        request = SearchQuery(
            query=cleaned_query,
            country=country.strip(),
            language=language.strip() or "en",
            max_results=max_results,
        )

        try:
            return self._provider.search(request)
        except Exception as error:
            return SearchResponse(
                success=False,
                provider_name=self._provider.provider_name,
                query=request,
                results=[],
                error_message=(
                    "The live search provider failed safely: "
                    f"{error}"
                ),
            )

    def search_many(
        self,
        queries: list[str],
        *,
        country: str = "",
        language: str = "en",
        max_results_per_query: int = 10,
    ) -> list[SearchResponse]:
        unique_queries = list(
            dict.fromkeys(
                " ".join(query.strip().split())
                for query in queries
                if query and query.strip()
            )
        )

        return [
            self.search(
                query,
                country=country,
                language=language,
                max_results=max_results_per_query,
            )
            for query in unique_queries
        ]


_gateway = GlobalSearchGateway()


def get_global_search_gateway() -> GlobalSearchGateway:
    """Return the configured global search gateway."""

    return _gateway


def configure_global_search_provider(
    provider: GlobalSearchProvider,
) -> None:
    """
    Replace the active provider at application startup.

    API credentials must be supplied through environment variables or
    a secrets manager, never committed to source control.
    """

    global _gateway
    _gateway = GlobalSearchGateway(provider)