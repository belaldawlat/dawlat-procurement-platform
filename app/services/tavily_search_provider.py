"""
Tavily live-search adapter for the Dawlat Procurement Platform.

The API key is loaded from the TAVILY_API_KEY environment variable.
Never hard-code or commit API keys.

This adapter uses Tavily's HTTPS Search endpoint through Python's
standard library, so it does not add another runtime dependency.
"""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from services.global_search_provider import (
    GlobalSearchProvider,
    SearchQuery,
    SearchResponse,
    SearchResult,
)


TAVILY_SEARCH_URL = "https://api.tavily.com/search"
DEFAULT_TIMEOUT_SECONDS = 30


class TavilySearchProvider(GlobalSearchProvider):
    """Approved Tavily implementation of the global-search contract."""

    provider_name = "Tavily"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        search_depth: str = "advanced",
    ) -> None:
        self._api_key = (
            api_key
            or os.getenv("TAVILY_API_KEY", "")
        ).strip()

        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be greater than zero."
            )

        if search_depth not in {"basic", "advanced"}:
            raise ValueError(
                "search_depth must be 'basic' or 'advanced'."
            )

        self._timeout_seconds = timeout_seconds
        self._search_depth = search_depth

    @property
    def is_configured(self) -> bool:
        """Return whether an API key is available."""

        return bool(self._api_key)

    def search(self, query: SearchQuery) -> SearchResponse:
        """Run one Tavily web search and normalize the response."""

        if not self.is_configured:
            return SearchResponse(
                success=False,
                provider_name=self.provider_name,
                query=query,
                error_message=(
                    "TAVILY_API_KEY is not configured. "
                    "Add it to your local .env file and restart the app."
                ),
            )

        payload = self._build_payload(query)

        request = Request(
            TAVILY_SEARCH_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": (
                    "Dawlat-Procurement-Platform/1.0"
                ),
            },
            method="POST",
        )

        try:
            with urlopen(
                request,
                timeout=self._timeout_seconds,
            ) as response:
                response_body = response.read().decode("utf-8")

            raw_data = json.loads(response_body)

        except HTTPError as error:
            return SearchResponse(
                success=False,
                provider_name=self.provider_name,
                query=query,
                error_message=self._http_error_message(error),
            )

        except URLError as error:
            return SearchResponse(
                success=False,
                provider_name=self.provider_name,
                query=query,
                error_message=(
                    "Unable to reach Tavily. "
                    f"Network error: {error.reason}"
                ),
            )

        except TimeoutError:
            return SearchResponse(
                success=False,
                provider_name=self.provider_name,
                query=query,
                error_message=(
                    "Tavily search timed out. Try again shortly."
                ),
            )

        except json.JSONDecodeError:
            return SearchResponse(
                success=False,
                provider_name=self.provider_name,
                query=query,
                error_message=(
                    "Tavily returned an invalid JSON response."
                ),
            )

        results = self._normalize_results(
            raw_data.get("results", []),
            maximum=query.max_results,
        )

        return SearchResponse(
            success=True,
            provider_name=self.provider_name,
            query=query,
            results=results,
        )

    def _build_payload(
        self,
        query: SearchQuery,
    ) -> dict[str, Any]:
        search_text = query.query

        if query.country:
            search_text = (
                f"{search_text} {query.country}"
            )

        return {
            "query": search_text,
            "search_depth": self._search_depth,
            "max_results": query.max_results,
            "include_answer": False,
            "include_raw_content": False,
            "include_images": False,
            "topic": "general",
        }

    @staticmethod
    def _normalize_results(
        raw_results: list[dict[str, Any]],
        *,
        maximum: int,
    ) -> list[SearchResult]:
        normalized: list[SearchResult] = []
        seen_urls: set[str] = set()

        for item in raw_results:
            url = str(item.get("url") or "").strip()
            title = str(item.get("title") or "").strip()

            if not url or not title or url in seen_urls:
                continue

            seen_urls.add(url)

            normalized.append(
                SearchResult(
                    title=title,
                    url=url,
                    snippet=str(
                        item.get("content") or ""
                    ).strip(),
                    source_name=_domain_from_url(url),
                    published_at=item.get("published_date"),
                    metadata={
                        "relevance_score": item.get("score"),
                    },
                )
            )

            if len(normalized) >= maximum:
                break

        return normalized

    @staticmethod
    def _http_error_message(
        error: HTTPError,
    ) -> str:
        response_body = ""

        try:
            response_body = error.read().decode(
                "utf-8",
                errors="replace",
            )
        except Exception:
            response_body = ""

        details = ""

        if response_body:
            try:
                parsed = json.loads(response_body)
                details = str(
                    parsed.get("detail")
                    or parsed.get("message")
                    or parsed.get("error")
                    or ""
                ).strip()
            except json.JSONDecodeError:
                details = response_body[:300].strip()

        status_messages = {
            400: "The Tavily search request was invalid.",
            401: "The Tavily API key was rejected.",
            403: "The Tavily account is not authorized for this request.",
            429: "The Tavily rate or credit limit was reached.",
        }

        base_message = status_messages.get(
            error.code,
            f"Tavily returned HTTP {error.code}.",
        )

        return (
            f"{base_message} {details}".strip()
        )


def _domain_from_url(url: str) -> str:
    """Return a readable domain without another dependency."""

    value = url.split("://", 1)[-1]
    return value.split("/", 1)[0].lower()


def create_tavily_provider() -> TavilySearchProvider:
    """Factory used at application startup."""

    return TavilySearchProvider()