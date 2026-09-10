"""Bounded, provider-agnostic external research for one analysis run."""

import json
import logging
import os
import time
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from urllib.error import URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, ValidationError

from models.evidence import Evidence, ResearchCategory, SourceQuality, SourceType
from services.evidence_store import EvidenceStore

logger = logging.getLogger(__name__)


class NormalizedSearchResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    url: HttpUrl
    excerpt: str
    relevance_score: float = Field(ge=0, le=1)
    publication_date: datetime | None = None


class ResearchProvider(ABC):
    name: str

    @abstractmethod
    def search(self, query: str, max_results: int) -> list[NormalizedSearchResult]:
        raise NotImplementedError


class ResearchProviderUnavailable(Exception):
    pass


class TavilyResearchProvider(ResearchProvider):
    """Minimal Tavily REST adapter; active only when TAVILY_API_KEY is configured."""

    name = "tavily"

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def search(self, query: str, max_results: int) -> list[NormalizedSearchResult]:
        payload = json.dumps({"query": query, "max_results": max_results, "search_depth": "basic"}).encode()
        request = Request(
            "https://api.tavily.com/search",
            data=payload,
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=15) as response:
                body = json.loads(response.read().decode())
        except (URLError, TimeoutError, json.JSONDecodeError) as error:
            raise ResearchProviderUnavailable("Tavily search failed") from error
        results = []
        for item in body.get("results", []):
            try:
                results.append(NormalizedSearchResult(
                    title=item["title"], url=item["url"], excerpt=item["content"],
                    relevance_score=float(item.get("score", 0)), publication_date=item.get("published_date"),
                ))
            except (KeyError, ValidationError, ValueError):
                continue
        return results


def configured_provider() -> ResearchProvider | None:
    key = os.getenv("TAVILY_API_KEY")
    return TavilyResearchProvider(key) if key else None


def classify_source(url: str) -> tuple[SourceType, SourceQuality]:
    host = url.split("//", 1)[-1].split("/", 1)[0].lower()
    if host.endswith(".gov"):
        return SourceType.GOVERNMENT, SourceQuality.HIGH
    if host.endswith(".edu") or ".ac." in host:
        return SourceType.ACADEMIC, SourceQuality.HIGH
    if any(marker in host for marker in ("linkedin.com", "reddit.com", "quora.com", "forum")):
        return SourceType.COMMUNITY, SourceQuality.LOW
    if any(marker in host for marker in ("reuters.com", "bloomberg.com", "ft.com", "wsj.com")):
        return SourceType.NEWS, SourceQuality.HIGH
    if any(marker in host for marker in ("statista.", "gartner.", "mckinsey.", "deloitte.")):
        return SourceType.INDUSTRY, SourceQuality.MEDIUM
    return SourceType.UNKNOWN, SourceQuality.UNKNOWN


def research_queries(startup_idea: str) -> list[tuple[ResearchCategory, str]]:
    subject = " ".join(startup_idea.split())[:180]
    topics = [
        (ResearchCategory.MARKET, "market size growth"), (ResearchCategory.CUSTOMERS, "target customer needs alternatives"),
        (ResearchCategory.COMPETITORS, "competitors alternatives"), (ResearchCategory.PRICING, "competitor pricing"),
        (ResearchCategory.INDUSTRY_TRENDS, "industry trends adoption"), (ResearchCategory.TECHNOLOGY, "technology landscape"),
        (ResearchCategory.BUSINESS_MODEL, "business model benchmarks"), (ResearchCategory.REGULATORY, "regulatory considerations"),
    ]
    return [(category, f"{subject} {suffix}") for category, suffix in topics]


class ResearchRun(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    status: str
    provider: str | None = None
    message: str
    store: EvidenceStore = Field(default_factory=EvidenceStore)


class ResearchEngine:
    def __init__(self, provider: ResearchProvider | None = None, max_results: int = 3) -> None:
        self.provider = provider if provider is not None else configured_provider()
        self.max_results = max_results

    def run(self, startup_idea: str) -> ResearchRun:
        store = EvidenceStore()
        if not self.provider:
            return ResearchRun(status="RESEARCH_UNAVAILABLE", message="No research provider is configured.", store=store)
        failures = 0
        started = time.perf_counter()
        for category, query in research_queries(startup_idea):
            try:
                results = self.provider.search(query, self.max_results)
                logger.info("research query provider=%s category=%s results=%d", self.provider.name, category.value, len(results))
            except ResearchProviderUnavailable:
                failures += 1
                continue
            for result in results:
                source_type, quality = classify_source(str(result.url))
                store.add(Evidence(evidence_id=store.next_id(), category=category, topic=query, title=result.title,
                    source_url=result.url, source_name=result.url.host, source_type=source_type, source_quality=quality,
                    excerpt=result.excerpt[:2000], relevance_score=result.relevance_score,
                    publication_date=result.publication_date, retrieved_at=datetime.now(timezone.utc)))
        logger.info("research complete provider=%s evidence=%d failures=%d latency_ms=%d", self.provider.name, len(store.list()), failures, int((time.perf_counter()-started)*1000))
        status = "RESEARCH_AVAILABLE" if failures == 0 else "RESEARCH_PARTIAL"
        return ResearchRun(status=status, provider=self.provider.name, message="Research completed." if store.list() else "Research returned no usable evidence.", store=store)


def evidence_package(store: EvidenceStore, categories: list[ResearchCategory]) -> str:
    items = [item for category in categories for item in store.list(category)]
    if not items:
        return "No external evidence is available. Do not make externally factual claims; state assumptions explicitly."
    return "\n".join(f"{item.evidence_id} | {item.category.value} | {item.title} | {item.excerpt}" for item in items[:12])
