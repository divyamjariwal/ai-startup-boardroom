"""4C -- reference-class discovery.

Turn a 4A :class:`IdeaProfile` into a small set of real, evidence-backed
comparable startups, each scored against the idea by the 4B similarity engine.

Deliberately minimal: **2 internet searches + 1 LLM call** per idea. The
internet evidence is the source of truth -- the LLM only *extracts* named
startups and their attributes from retrieved excerpts and must cite the
evidence ids it used; it never invents companies or facts. Everything after the
searches and that one extraction call is deterministic (query generation,
evidence storage, id resolution, attribute normalisation, dedup, similarity,
relevance filtering, status).

Reuses, does not rebuild:

* internet search + provider abstraction -- ``services.research``
  (``ResearchProvider``, ``configured_provider``, ``classify_source``)
* evidence / source storage -- ``models.evidence.Evidence`` +
  ``services.evidence_store.EvidenceStore`` (URL-dedup, ``E-###`` ids)
* the one LLM call -- ``agents.base_agent.run_agent`` + a single prompt file
* candidate contract + scoring -- ``models.reference_class.CandidateProfile`` /
  ``VerifiedCandidate`` / ``DroppedCandidate`` and
  ``services.similarity.score_similarity`` / ``is_relevant``

4C does **not** build a ``ReferenceClass`` (that needs 4D outcome
classification). It returns a ``DiscoveryResult`` holding ``VerifiedCandidate``
objects (discovered + similarity-scored, not yet outcome-classified).
"""

import logging
from collections.abc import Callable
from datetime import date, datetime, timezone

from pydantic import BaseModel, ConfigDict, Field, model_validator

from agents.base_agent import run_agent
from models.evidence import Evidence, ResearchCategory
from models.reference_class import (
    SIMILARITY_INCLUSION_THRESHOLD,
    BusinessModel,
    CandidateProfile,
    CustomerType,
    DroppedCandidate,
    DropReason,
    IdeaProfile,
    ProductForm,
    ReferenceClassStatus,
    VerifiedCandidate,
)
from services.evidence_store import EvidenceStore
from services.idea_profile import GEO_REGION_LABELS, INDUSTRY_TAGS
from services.research import (
    ResearchProvider,
    ResearchProviderUnavailable,
    classify_source,
    configured_provider,
)
from services.similarity import is_relevant, score_similarity

logger = logging.getLogger(__name__)

# Bounded and cheap on purpose: 2 searches + 1 LLM call per idea.
MAX_DISCOVERY_QUERIES = 2
DISCOVERY_RESULTS_PER_QUERY = 5
MAX_CANDIDATES = 6
# Comparable startups are, in the existing taxonomy, a competitors/alternatives topic.
DISCOVERY_CATEGORY = ResearchCategory.COMPETITORS

_EARLIEST_FOUNDING_YEAR = 1990
_ONE_LINER_MAX = 200

# Common LLM geography phrasings -> canonical GEO_REGION_LABELS entries.
_GEO_ALIASES: dict[str, str] = {
    "usa": "United States",
    "u.s.": "United States",
    "u.s": "United States",
    "us": "United States",
    "america": "United States",
    "united states of america": "United States",
    "uk": "United Kingdom",
    "u.k.": "United Kingdom",
    "britain": "United Kingdom",
    "england": "United Kingdom",
    "eu": "European Union",
    "europe": "European Union",
    "worldwide": "Global",
    "international": "Global",
    "global": "Global",
}


# --------------------------------------------------------------------------- #
# LLM extraction contract (lenient on purpose -- the strict gate downstream is
# models.reference_class.CandidateProfile).
# --------------------------------------------------------------------------- #
class ExtractedCandidate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = ""
    one_liner: str = ""
    industry: str = "unspecified"
    geography: str | None = None
    business_model: str = "unknown"
    product_form: str = "unknown"
    customer_type: str = "unknown"
    customer_descriptor: str | None = None
    founding_year: int | None = None
    supporting_evidence_ids: list[str] = Field(default_factory=list)


class CandidateExtraction(BaseModel):
    model_config = ConfigDict(extra="ignore")

    candidates: list[ExtractedCandidate] = Field(default_factory=list)


class DiscoveryResult(BaseModel):
    """4C output. Mirrors ``services.research.ResearchRun``: a status + message +
    its own per-run :class:`EvidenceStore`, plus the discovered candidates."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    idea_profile: IdeaProfile
    status: ReferenceClassStatus
    candidates: list[VerifiedCandidate] = Field(default_factory=list)
    dropped: list[DroppedCandidate] = Field(default_factory=list)
    evidence_store: EvidenceStore
    search_count: int = Field(ge=0)
    llm_calls: int = Field(ge=0)
    message: str

    @model_validator(mode="after")
    def _check_no_provider(self) -> "DiscoveryResult":
        if self.status is ReferenceClassStatus.UNAVAILABLE_NO_PROVIDER and (
            self.candidates or self.dropped or self.search_count or self.llm_calls
        ):
            raise ValueError(
                "UNAVAILABLE_NO_PROVIDER implies no candidates/dropped and zero "
                "searches / llm calls"
            )
        return self


ExtractorFn = Callable[[IdeaProfile, list[Evidence]], CandidateExtraction]


# --------------------------------------------------------------------------- #
# Deterministic query generation
# --------------------------------------------------------------------------- #
def discovery_queries(idea: IdeaProfile) -> list[str]:
    """Exactly ``MAX_DISCOVERY_QUERIES`` non-empty, distinct search queries."""

    keywords = " ".join(idea.keywords[:4]).strip()
    subject_bits = [
        bit for bit in (idea.customer_descriptor, idea.problem) if bit and bit != "unspecified"
    ]
    if keywords:
        subject_bits.append(keywords)
    subject = "; ".join(subject_bits) or idea.raw_text[:160].strip()
    q1 = f"startups similar to {subject}".strip()

    parts: list[str] = []
    if idea.industry != "unspecified":
        parts.append(idea.industry)
    parts.append("startups")
    if idea.product_form is not ProductForm.UNKNOWN:
        parts.append(idea.product_form.value)
    if keywords:
        parts.append(keywords)
    q2 = " ".join(parts).strip()
    if q2 in ("", "startups"):
        q2 = f"companies like: {idea.raw_text[:150]}".strip()
    if q2.lower() == q1.lower():
        q2 = f"real companies comparable to {subject} market".strip()

    return [q1, q2][:MAX_DISCOVERY_QUERIES]


# --------------------------------------------------------------------------- #
# The one LLM call
# --------------------------------------------------------------------------- #
def _idea_summary(idea: IdeaProfile) -> str:
    return (
        f"industry={idea.industry}; product_form={idea.product_form.value}; "
        f"business_model={idea.business_model.value}; "
        f"customer_type={idea.customer_type.value}; "
        f"customer_descriptor={idea.customer_descriptor}; problem={idea.problem}; "
        f"geography={idea.geography}; keywords={', '.join(idea.keywords)}"
    )


def _evidence_block(evidence: list[Evidence]) -> str:
    return "\n\n".join(
        f"[{item.evidence_id}] {item.title} -- {item.source_url}\n{item.excerpt.strip()}"
        for item in evidence
    )


def extract_candidates(idea: IdeaProfile, evidence: list[Evidence]) -> CandidateExtraction:
    """One Groq call: pull real comparable startups out of the retrieved evidence."""

    user_input = (
        f"<STARTUP_IDEA_PROFILE>\n{_idea_summary(idea)}\n</STARTUP_IDEA_PROFILE>\n\n"
        f"<SEARCH_EVIDENCE>\n{_evidence_block(evidence)}\n</SEARCH_EVIDENCE>"
    )
    return run_agent(
        "prompts/reference_class_extraction.txt", user_input, CandidateExtraction
    )


# --------------------------------------------------------------------------- #
# Deterministic normalisation of extracted attributes
# --------------------------------------------------------------------------- #
def _normalize_industry(raw: str | None) -> str:
    if not raw:
        return "unspecified"
    value = raw.strip().lower().replace(" ", "_").replace("-", "_")
    return value if value in INDUSTRY_TAGS else "unspecified"


def _normalize_geography(raw: str | None) -> str | None:
    if not raw:
        return None
    value = raw.strip()
    for label in GEO_REGION_LABELS:
        if value.lower() == label.lower():
            return label
    return _GEO_ALIASES.get(value.lower())


def _normalize_enum(raw: str | None, enum_cls, unknown):
    if not raw:
        return unknown
    value = raw.strip().lower()
    for member in enum_cls:
        if member.value == value:
            return member
    return unknown


def _clean_descriptor(raw: str | None) -> str | None:
    if not raw:
        return None
    value = " ".join(raw.split()).strip()
    if not value or value.lower() in ("unspecified", "unknown", "n/a", "none"):
        return None
    return value[:120]


def _dedupe_key(name: str) -> str:
    value = " ".join(name.split()).strip().lower().rstrip(".,")
    for suffix in (" inc", " llc", " ltd", " corp", " co", " gmbh", " limited"):
        if value.endswith(suffix):
            value = value[: -len(suffix)].rstrip(".,").strip()
    return value


def _founding_year(raw: int | None) -> int | None:
    if raw is None:
        return None
    if _EARLIEST_FOUNDING_YEAR <= raw <= date.today().year + 1:
        return raw
    return None


# --------------------------------------------------------------------------- #
# Orchestrator
# --------------------------------------------------------------------------- #
def discover_reference_class(
    idea: IdeaProfile,
    *,
    provider: ResearchProvider | None = None,
    extractor: ExtractorFn | None = None,
) -> DiscoveryResult:
    """Discover evidence-backed comparable startups for ``idea``.

    ``provider`` / ``extractor`` default to the real Tavily provider and the real
    Groq extraction call; both are injectable so tests never touch the network.
    """

    resolved_provider = provider if provider is not None else configured_provider()
    store = EvidenceStore()

    if resolved_provider is None:
        return DiscoveryResult(
            idea_profile=idea,
            status=ReferenceClassStatus.UNAVAILABLE_NO_PROVIDER,
            evidence_store=store,
            search_count=0,
            llm_calls=0,
            message="No research provider is configured; reference-class discovery skipped.",
        )

    resolved_extractor = extractor if extractor is not None else extract_candidates
    queries = discovery_queries(idea)

    shown: list[Evidence] = []
    failures = 0
    for query in queries:
        try:
            results = resolved_provider.search(query, DISCOVERY_RESULTS_PER_QUERY)
        except ResearchProviderUnavailable:
            failures += 1
            continue
        for result in results:
            source_type, quality = classify_source(str(result.url))
            added = store.add(
                Evidence(
                    evidence_id=store.next_id(),
                    category=DISCOVERY_CATEGORY,
                    topic=query,
                    title=result.title,
                    source_url=result.url,
                    source_name=result.url.host,
                    source_type=source_type,
                    source_quality=quality,
                    excerpt=result.excerpt[:2000],
                    relevance_score=result.relevance_score,
                    publication_date=result.publication_date,
                    retrieved_at=datetime.now(timezone.utc),
                )
            )
            if added is not None:
                shown.append(added)

    search_count = len(queries) - failures
    logger.info(
        "reference discovery: queries=%d failures=%d evidence=%d",
        len(queries),
        failures,
        len(shown),
    )

    if not shown:
        message = (
            "Every reference-class search failed."
            if failures == len(queries)
            else "No usable search results for reference-class discovery."
        )
        return DiscoveryResult(
            idea_profile=idea,
            status=ReferenceClassStatus.UNAVAILABLE_NO_MATCHES,
            evidence_store=store,
            search_count=search_count,
            llm_calls=0,
            message=message,
        )

    try:
        extraction = resolved_extractor(idea, shown)
    except Exception as error:  # feature-degradation boundary -- never crash the boardroom
        logger.warning("reference-class extraction failed: %s", error)
        return DiscoveryResult(
            idea_profile=idea,
            status=ReferenceClassStatus.UNAVAILABLE_NO_MATCHES,
            evidence_store=store,
            search_count=search_count,
            llm_calls=1,
            message="Comparable-startup extraction failed; evidence retained but no candidates.",
        )

    by_id = {item.evidence_id: item for item in shown}
    kept: list[VerifiedCandidate] = []
    dropped: list[DroppedCandidate] = []
    seen: dict[str, str] = {}

    for raw in extraction.candidates[:MAX_CANDIDATES]:
        name = " ".join(raw.name.split()).strip()[:120]
        if not name:
            continue

        key = _dedupe_key(name)
        if key in seen:
            dropped.append(
                DroppedCandidate(
                    name=name,
                    reason=DropReason.DUPLICATE,
                    detail=f"Duplicate of '{seen[key]}'.",
                    merged_into=seen[key],
                )
            )
            continue

        evidence_ids = list(
            dict.fromkeys(eid for eid in raw.supporting_evidence_ids if eid in by_id)
        )
        if not evidence_ids:
            dropped.append(
                DroppedCandidate(
                    name=name,
                    reason=DropReason.NOT_VERIFIED_AS_COMPANY,
                    detail="No retrieved evidence supports this startup.",
                )
            )
            continue

        one_liner = (
            " ".join(raw.one_liner.split()).strip()
            or by_id[evidence_ids[0]].excerpt.strip()
        )[:_ONE_LINER_MAX]
        if not one_liner:
            dropped.append(
                DroppedCandidate(
                    name=name,
                    reason=DropReason.NOT_VERIFIED_AS_COMPANY,
                    detail="No description could be sourced from evidence.",
                    evidence_ids=evidence_ids,
                )
            )
            continue

        profile = CandidateProfile(
            name=name,
            one_liner=one_liner,
            industry=_normalize_industry(raw.industry),
            geography=_normalize_geography(raw.geography),
            business_model=_normalize_enum(raw.business_model, BusinessModel, BusinessModel.UNKNOWN),
            product_form=_normalize_enum(raw.product_form, ProductForm, ProductForm.UNKNOWN),
            customer_type=_normalize_enum(raw.customer_type, CustomerType, CustomerType.UNKNOWN),
            customer_descriptor=_clean_descriptor(raw.customer_descriptor),
        )
        breakdown = score_similarity(idea, profile)
        relevant = is_relevant(breakdown)
        seen[key] = profile.name

        if not relevant:
            dropped.append(
                DroppedCandidate(
                    name=profile.name,
                    reason=DropReason.INSUFFICIENT_RELEVANCE,
                    detail=(
                        f"Similarity {breakdown.total} below inclusion threshold "
                        f"{SIMILARITY_INCLUSION_THRESHOLD}."
                    ),
                    evidence_ids=evidence_ids,
                )
            )
            continue

        kept.append(
            VerifiedCandidate(
                name=profile.name,
                one_liner=profile.one_liner,
                industry=profile.industry,
                geography=profile.geography,
                business_model=profile.business_model,
                product_form=profile.product_form,
                customer_type=profile.customer_type,
                customer_descriptor=profile.customer_descriptor,
                founding_year=_founding_year(raw.founding_year),
                similarity=breakdown,
                evidence_ids=evidence_ids,
                is_company_verified=True,
                is_relevant=True,
            )
        )

    if not kept:
        status = ReferenceClassStatus.UNAVAILABLE_NO_MATCHES
        message = "No comparable startups cleared discovery and relevance filtering."
    elif failures > 0:
        status = ReferenceClassStatus.PARTIAL
        message = (
            f"{len(kept)} comparable startup(s) identified; "
            f"{failures} of {len(queries)} searches failed."
        )
    else:
        status = ReferenceClassStatus.AVAILABLE
        message = (
            f"{len(kept)} comparable startup(s) identified from {len(shown)} sources."
        )

    return DiscoveryResult(
        idea_profile=idea,
        status=status,
        candidates=kept,
        dropped=dropped,
        evidence_store=store,
        search_count=search_count,
        llm_calls=1,
        message=message,
    )
