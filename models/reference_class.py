"""Typed data layer for the historical reference-class feature (Step 4A).

This module defines *only* data contracts and named constants. It carries no
discovery, similarity, verification, or aggregation logic -- those arrive in
later steps (4B-4E). The reference class is a **descriptive** evidence layer
that is deliberately kept independent of specialist scoring and the assumption
engine; nothing defined here feeds those systems.

Design rules baked into the types:

* Outcomes are descriptive, never predictive. ``OutcomePolarity`` is a separate
  axis from ``StartupOutcome`` -- "acquired" / "active" are not "success".
* No success probabilities anywhere. ``_reject_forbidden`` blocks predictive
  phrasing in every human-readable field.
* ``PatternConfidence`` never exceeds ``MEDIUM``. A ``LOW`` pattern must be
  phrased by its producer (Step 4E) as a bounded observation about the
  retrieved sample -- e.g. "2 of the 6 retrieved comparables pivoted" -- never
  a population-level claim and never anything implying predictive power.
* ``ReferenceClassStatus.PARTIAL`` is an *engine* invariant (at least one
  provider call raised ``ResearchProviderUnavailable`` during the run); the
  model neither proves it nor carries a field for it.
* Evidence traceability: every ``evidence_id`` on a comparable or dropped
  candidate must resolve in the run's separate reference ``EvidenceStore``.
"""

import math
from datetime import date
from enum import Enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from models.evidence import SourceQuality
from services.evidence_store import EvidenceStore


# --------------------------------------------------------------------------- #
# Enums
# --------------------------------------------------------------------------- #
class StartupOutcome(str, Enum):
    ACTIVE = "active"
    ACQUIRED = "acquired"
    PUBLIC = "public"
    SHUT_DOWN = "shut_down"
    PIVOTED = "pivoted"
    UNKNOWN = "unknown"


class OutcomePolarity(str, Enum):
    """Soft, summary-only axis. Never merged into ``StartupOutcome`` and never
    read as success/failure."""

    CONTINUED = "continued"
    ENDED = "ended"
    UNCLEAR = "unclear"


class ReferenceClassStatus(str, Enum):
    AVAILABLE = "available"
    PARTIAL = "partial"  # engine invariant: >=1 ResearchProviderUnavailable this run
    UNAVAILABLE_NO_PROVIDER = "unavailable_no_provider"
    UNAVAILABLE_NO_MATCHES = "unavailable_no_matches"


class ProductForm(str, Enum):
    APP = "app"
    SAAS = "saas"
    MARKETPLACE = "marketplace"
    API = "api"
    HARDWARE = "hardware"
    PLATFORM = "platform"
    SERVICE = "service"
    CONTENT = "content"
    UNKNOWN = "unknown"


class BusinessModel(str, Enum):
    SUBSCRIPTION = "subscription"
    MARKETPLACE = "marketplace"
    TRANSACTIONAL = "transactional"
    ADVERTISING = "advertising"
    FREEMIUM = "freemium"
    HARDWARE = "hardware"
    SERVICES = "services"
    LICENSING = "licensing"
    UNKNOWN = "unknown"


class CustomerType(str, Enum):
    CONSUMER = "consumer"
    BUSINESS = "business"
    DEVELOPER = "developer"
    PUBLIC_SECTOR = "public_sector"
    UNKNOWN = "unknown"


class SimilarityDimension(str, Enum):
    PROBLEM = "problem"
    CUSTOMER = "customer"
    INDUSTRY = "industry"
    PRODUCT_FORM = "product_form"
    BUSINESS_MODEL = "business_model"
    GEOGRAPHY = "geography"


class ComparableFlag(str, Enum):
    NAME_AMBIGUOUS = "name_ambiguous"
    SINGLE_SOURCE = "single_source"
    WEAK_SOURCES = "weak_sources"
    CONFLICTING_OUTCOME = "conflicting_outcome"
    PIVOT = "pivot"


class DropReason(str, Enum):
    NOT_VERIFIED_AS_COMPANY = "not_verified_as_company"
    INSUFFICIENT_RELEVANCE = "insufficient_relevance"
    NO_EVIDENCE_RETRIEVED = "no_evidence_retrieved"
    NAME_TOO_AMBIGUOUS = "name_too_ambiguous"
    DUPLICATE = "duplicate"
    BUDGET_CAP_REACHED = "budget_cap_reached"


class PatternType(str, Enum):
    OUTCOME_TENDENCY = "outcome_tendency"
    RECURRING_RISK = "recurring_risk"
    COMMON_PIVOT = "common_pivot"
    GTM_PATTERN = "gtm_pattern"


class PatternConfidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"


class UnresolvedField(str, Enum):
    CUSTOMER_TYPE = "customer_type"
    CUSTOMER_DESCRIPTOR = "customer_descriptor"
    PROBLEM = "problem"
    PRODUCT_FORM = "product_form"
    BUSINESS_MODEL = "business_model"
    INDUSTRY = "industry"
    GEOGRAPHY = "geography"


# --------------------------------------------------------------------------- #
# Named constants -- the single source of truth for every cap / knob.
# --------------------------------------------------------------------------- #
MAX_COMPARABLES = 8
MIN_DISCOVERY_QUERIES = 3
MAX_DISCOVERY_QUERIES = 4
DISCOVERY_RESULTS_PER_QUERY = 5
MAX_VERIFICATION_SEARCHES = 8
VERIFICATION_RESULTS_PER_CANDIDATE = 3
MAX_PATTERNS = 12

SIMILARITY_WEIGHTS: dict[SimilarityDimension, float] = {
    SimilarityDimension.PROBLEM: 0.25,
    SimilarityDimension.CUSTOMER: 0.20,
    SimilarityDimension.INDUSTRY: 0.20,
    SimilarityDimension.PRODUCT_FORM: 0.15,
    SimilarityDimension.BUSINESS_MODEL: 0.15,
    SimilarityDimension.GEOGRAPHY: 0.05,
}
SIMILARITY_MATCH_THRESHOLD = 0.60
SIMILARITY_DIVERGENT_THRESHOLD = 0.30
SIMILARITY_INCLUSION_THRESHOLD = 45
UNKNOWN_DIMENSION_SCORE = 0.30

PATTERN_MIN_SUPPORT = 2
PATTERN_MEDIUM_CONFIDENCE_MIN_SUPPORT = 3

OUTCOME_UNKNOWN_MAX_CONFIDENCE = 0.20
ACTIVE_SIGNAL_RECENCY_MONTHS = 24
EARLIEST_PLAUSIBLE_YEAR = 1990

POLARITY_BY_OUTCOME: dict[StartupOutcome, OutcomePolarity] = {
    StartupOutcome.ACTIVE: OutcomePolarity.CONTINUED,
    StartupOutcome.ACQUIRED: OutcomePolarity.CONTINUED,
    StartupOutcome.PUBLIC: OutcomePolarity.CONTINUED,
    StartupOutcome.SHUT_DOWN: OutcomePolarity.ENDED,
    StartupOutcome.PIVOTED: OutcomePolarity.UNCLEAR,
    StartupOutcome.UNKNOWN: OutcomePolarity.UNCLEAR,
}

# Canonical display / storage order for IdeaProfile.unresolved_fields. Shared by
# services.idea_profile so the builder and the validator agree.
UNRESOLVED_FIELD_ORDER: tuple[UnresolvedField, ...] = (
    UnresolvedField.CUSTOMER_TYPE,
    UnresolvedField.CUSTOMER_DESCRIPTOR,
    UnresolvedField.PROBLEM,
    UnresolvedField.PRODUCT_FORM,
    UnresolvedField.BUSINESS_MODEL,
    UnresolvedField.INDUSTRY,
    UnresolvedField.GEOGRAPHY,
)

REFERENCE_CLASS_DISCLAIMER = (
    "Descriptive evidence layer. These are search-derived comparable startups, "
    "not a statistically representative sample. Outcomes describe what appears "
    "to have happened; they are not predictions and not success probabilities. "
    "'Active' does not mean successful."
)

# Case-insensitive substrings rejected in every human-readable field: the
# reference class is descriptive, never predictive.
FORBIDDEN_DESCRIPTIVE_PHRASES: tuple[str, ...] = (
    "success probability",
    "probability of success",
    "chance of success",
    "odds of success",
    "success rate",
    "% success",
    "likely to succeed",
    "will succeed",
    "guaranteed",
)


def _reject_forbidden(text: str) -> None:
    lowered = text.lower()
    for phrase in FORBIDDEN_DESCRIPTIVE_PHRASES:
        if phrase in lowered:
            raise ValueError(
                f"text may not contain the phrase {phrase!r}: reference-class "
                f"output is descriptive, not predictive"
            )


def build_summary_narrative(
    *,
    total_comparables: int,
    continued_count: int,
    ended_count: int,
    unclear_count: int,
    dropped_count: int,
) -> str:
    """Deterministic, neutral summary sentence.

    The middle sentence is emitted only when candidates were actually dropped.
    Wording is intentionally reason-agnostic (candidates can be excluded as
    unverifiable, off-topic, duplicates, or by a hard budget cap).
    """

    sentences = [
        f"Among the {total_comparables} verified comparable startups retrieved "
        f"for this idea, {continued_count} had continued outcomes, "
        f"{ended_count} had ended outcomes, and {unclear_count} remained unclear."
    ]
    if dropped_count:
        sentences.append(
            f"{dropped_count} further candidate(s) were excluded during "
            f"verification or relevance filtering."
        )
    sentences.append(
        "This sample is search-derived and is not a statistically "
        "representative population of similar startups."
    )
    return " ".join(sentences)


def _not_future_year(year: int | None, field_name: str) -> None:
    if year is not None and year > date.today().year + 1:
        raise ValueError(f"{field_name} is implausibly far in the future")


# --------------------------------------------------------------------------- #
# Similarity
# --------------------------------------------------------------------------- #
class DimensionScore(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    dimension: SimilarityDimension
    score: Annotated[float, Field(ge=0.0, le=1.0)]
    weight: Annotated[float, Field(ge=0.0, le=1.0)]
    weighted_score: Annotated[float, Field(ge=0.0, le=1.0)]
    basis: Annotated[str, Field(min_length=1, max_length=200)]

    @model_validator(mode="after")
    def _check_weighted_score(self) -> "DimensionScore":
        if not math.isclose(self.weighted_score, self.score * self.weight, abs_tol=1e-6):
            raise ValueError("weighted_score must equal score * weight")
        return self


class SimilarityBreakdown(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    dimensions: Annotated[list[DimensionScore], Field(min_length=6, max_length=6)]
    total: Annotated[int, Field(ge=0, le=100)]
    matched_dimensions: list[SimilarityDimension] = Field(default_factory=list)
    divergent_dimensions: list[SimilarityDimension] = Field(default_factory=list)
    rationale: Annotated[str, Field(min_length=1, max_length=600)]

    @model_validator(mode="after")
    def _check_breakdown(self) -> "SimilarityBreakdown":
        dims = [d.dimension for d in self.dimensions]
        if len(set(dims)) != len(dims) or set(dims) != set(SimilarityDimension):
            raise ValueError(
                "dimensions must contain each SimilarityDimension exactly once"
            )
        for d in self.dimensions:
            expected_weight = SIMILARITY_WEIGHTS[d.dimension]
            if not math.isclose(d.weight, expected_weight, abs_tol=1e-9):
                raise ValueError(
                    f"weight for {d.dimension.value} must be {expected_weight}"
                )
        expected_total = round(100 * sum(d.weighted_score for d in self.dimensions))
        if self.total != expected_total:
            raise ValueError(f"total must equal {expected_total}")
        expected_matched = [
            d.dimension for d in self.dimensions if d.score >= SIMILARITY_MATCH_THRESHOLD
        ]
        expected_divergent = [
            d.dimension
            for d in self.dimensions
            if d.score <= SIMILARITY_DIVERGENT_THRESHOLD
        ]
        if self.matched_dimensions != expected_matched:
            raise ValueError(
                "matched_dimensions must be exactly the dimensions scoring "
                ">= SIMILARITY_MATCH_THRESHOLD, in dimensions order"
            )
        if self.divergent_dimensions != expected_divergent:
            raise ValueError(
                "divergent_dimensions must be exactly the dimensions scoring "
                "<= SIMILARITY_DIVERGENT_THRESHOLD, in dimensions order"
            )
        _reject_forbidden(self.rationale)
        return self


# --------------------------------------------------------------------------- #
# Outcome verification
# --------------------------------------------------------------------------- #
class OutcomeSignal(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    outcome: StartupOutcome
    phrase: Annotated[str, Field(min_length=1, max_length=120)]
    evidence_id: Annotated[str, Field(pattern=r"^E-\d{3}$")]
    source_quality: SourceQuality
    detected_year: Annotated[int, Field(ge=EARLIEST_PLAUSIBLE_YEAR)] | None = None

    @model_validator(mode="after")
    def _check_signal(self) -> "OutcomeSignal":
        if self.outcome is StartupOutcome.UNKNOWN:
            raise ValueError(
                "a recorded OutcomeSignal must point to a concrete outcome, "
                "not UNKNOWN"
            )
        _not_future_year(self.detected_year, "detected_year")
        return self


class OutcomeAssessment(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    outcome: StartupOutcome
    polarity: OutcomePolarity
    outcome_year: Annotated[int, Field(ge=EARLIEST_PLAUSIBLE_YEAR)] | None = None
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    supporting_evidence_ids: list[Annotated[str, Field(pattern=r"^E-\d{3}$")]] = Field(
        default_factory=list
    )
    signals: list[OutcomeSignal] = Field(default_factory=list)
    rationale: Annotated[str, Field(min_length=1, max_length=600)]
    conflicting: bool = False

    @model_validator(mode="after")
    def _check_assessment(self) -> "OutcomeAssessment":
        if self.polarity is not POLARITY_BY_OUTCOME[self.outcome]:
            raise ValueError(
                f"polarity for {self.outcome.value} must be "
                f"{POLARITY_BY_OUTCOME[self.outcome].value}"
            )
        _not_future_year(self.outcome_year, "outcome_year")
        if self.outcome is StartupOutcome.UNKNOWN:
            if self.confidence > OUTCOME_UNKNOWN_MAX_CONFIDENCE:
                raise ValueError(
                    "an UNKNOWN outcome must keep confidence "
                    f"<= {OUTCOME_UNKNOWN_MAX_CONFIDENCE}"
                )
            if self.outcome_year is not None:
                raise ValueError("an UNKNOWN outcome cannot carry an outcome_year")
            if self.supporting_evidence_ids:
                raise ValueError("an UNKNOWN outcome cannot cite supporting evidence")
        elif not self.supporting_evidence_ids:
            raise ValueError(
                "a concrete outcome must cite at least one supporting evidence id"
            )
        signal_ids = {s.evidence_id for s in self.signals}
        if self.supporting_evidence_ids and not set(self.supporting_evidence_ids) <= signal_ids:
            raise ValueError(
                "supporting_evidence_ids must all appear among signals[].evidence_id"
            )
        supporting = set(self.supporting_evidence_ids)
        for s in self.signals:
            if s.evidence_id in supporting and s.outcome is not self.outcome:
                raise ValueError(
                    "a supporting signal must point to the assessment's own outcome"
                )
        _reject_forbidden(self.rationale)
        return self


# --------------------------------------------------------------------------- #
# Candidate pipeline: raw candidate -> verified candidate -> comparable / dropped
# --------------------------------------------------------------------------- #
class RawCandidate(BaseModel):
    """A name pulled from a discovery search result. Not yet a company, not yet
    a comparable."""

    model_config = ConfigDict(extra="forbid", strict=True)

    name: Annotated[str, Field(min_length=1, max_length=120)]
    normalized_name: Annotated[str, Field(min_length=1, max_length=120)]
    aliases: list[Annotated[str, Field(min_length=1, max_length=120)]] = Field(
        default_factory=list, max_length=10
    )
    discovery_evidence_ids: Annotated[
        list[Annotated[str, Field(pattern=r"^E-\d{3}$")]], Field(min_length=1)
    ]
    mention_count: Annotated[int, Field(ge=1)]

    @model_validator(mode="after")
    def _check_normalized_name(self) -> "RawCandidate":
        if self.normalized_name != " ".join(self.normalized_name.split()):
            raise ValueError("normalized_name must be whitespace-collapsed and trimmed")
        if self.normalized_name != self.normalized_name.lower():
            raise ValueError("normalized_name must be lowercased")
        return self


class VerifiedCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: Annotated[str, Field(min_length=1, max_length=120)]
    aliases: list[Annotated[str, Field(min_length=1, max_length=120)]] = Field(
        default_factory=list, max_length=10
    )
    one_liner: Annotated[str, Field(min_length=1, max_length=200)]
    industry: Annotated[str, Field(min_length=1, max_length=40)]
    geography: Annotated[str, Field(min_length=1, max_length=60)] | None = None
    business_model: BusinessModel = BusinessModel.UNKNOWN
    product_form: ProductForm = ProductForm.UNKNOWN
    customer_type: CustomerType = CustomerType.UNKNOWN
    customer_descriptor: Annotated[str, Field(min_length=1, max_length=120)] | None = None
    founding_year: Annotated[int, Field(ge=EARLIEST_PLAUSIBLE_YEAR)] | None = None
    similarity: SimilarityBreakdown
    evidence_ids: Annotated[
        list[Annotated[str, Field(pattern=r"^E-\d{3}$")]], Field(min_length=1)
    ]
    is_company_verified: bool
    is_relevant: bool
    flags: list[ComparableFlag] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_candidate(self) -> "VerifiedCandidate":
        _not_future_year(self.founding_year, "founding_year")
        if self.is_relevant != (self.similarity.total >= SIMILARITY_INCLUSION_THRESHOLD):
            raise ValueError(
                "is_relevant must equal similarity.total >= "
                "SIMILARITY_INCLUSION_THRESHOLD"
            )
        return self


class ComparableStartup(VerifiedCandidate):
    """Only verified, relevant candidates with a classified outcome reach
    ``ReferenceClass.comparables``."""

    outcome: OutcomeAssessment

    @model_validator(mode="after")
    def _check_comparable(self) -> "ComparableStartup":
        if not self.is_company_verified:
            raise ValueError("a ComparableStartup must be a verified company")
        if not self.is_relevant:
            raise ValueError("a ComparableStartup must clear the relevance threshold")
        if not set(self.outcome.supporting_evidence_ids) <= set(self.evidence_ids):
            raise ValueError(
                "outcome.supporting_evidence_ids must be a subset of evidence_ids"
            )
        if (ComparableFlag.CONFLICTING_OUTCOME in self.flags) != self.outcome.conflicting:
            raise ValueError(
                "CONFLICTING_OUTCOME flag and outcome.conflicting must agree"
            )
        if ComparableFlag.PIVOT in self.flags:
            if (
                self.outcome.outcome is not StartupOutcome.PIVOTED
                and "pivot" not in self.outcome.rationale.lower()
            ):
                raise ValueError(
                    "PIVOT flag requires a PIVOTED outcome or a pivot mention in "
                    "the outcome rationale"
                )
        return self


class DroppedCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    name: Annotated[str, Field(min_length=1, max_length=120)]
    reason: DropReason
    detail: Annotated[str, Field(min_length=1, max_length=300)]
    evidence_ids: list[Annotated[str, Field(pattern=r"^E-\d{3}$")]] = Field(
        default_factory=list
    )
    merged_into: Annotated[str, Field(min_length=1, max_length=120)] | None = None

    @model_validator(mode="after")
    def _check_dropped(self) -> "DroppedCandidate":
        if (self.reason is DropReason.DUPLICATE) != (self.merged_into is not None):
            raise ValueError(
                "merged_into must be set if and only if reason is DUPLICATE"
            )
        return self


# --------------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------------- #
class ReferenceClassPattern(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    id: Annotated[str, Field(pattern=r"^RCP-\d{2}$")]
    text: Annotated[str, Field(min_length=1, max_length=400)]
    pattern_type: PatternType
    supporting_startups: Annotated[
        list[Annotated[str, Field(min_length=1, max_length=120)]],
        Field(min_length=PATTERN_MIN_SUPPORT),
    ]
    support_count: Annotated[int, Field(ge=PATTERN_MIN_SUPPORT)]
    confidence: PatternConfidence
    linked_assumption_hint: Annotated[str, Field(min_length=1, max_length=40)] | None = None

    @model_validator(mode="after")
    def _check_pattern(self) -> "ReferenceClassPattern":
        if self.support_count != len(self.supporting_startups):
            raise ValueError("support_count must equal len(supporting_startups)")
        if len(set(self.supporting_startups)) != len(self.supporting_startups):
            raise ValueError("supporting_startups must be unique")
        if (
            self.confidence is PatternConfidence.MEDIUM
            and self.support_count < PATTERN_MEDIUM_CONFIDENCE_MIN_SUPPORT
        ):
            raise ValueError(
                "MEDIUM confidence requires support_count >= "
                "PATTERN_MEDIUM_CONFIDENCE_MIN_SUPPORT"
            )
        _reject_forbidden(self.text)
        return self


class ReferenceClassSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    total_comparables: Annotated[int, Field(ge=0)]
    by_outcome: dict[StartupOutcome, Annotated[int, Field(ge=0)]]
    continued_count: Annotated[int, Field(ge=0)]
    ended_count: Annotated[int, Field(ge=0)]
    unclear_count: Annotated[int, Field(ge=0)]
    dropped_count: Annotated[int, Field(ge=0)]
    narrative: Annotated[str, Field(min_length=1, max_length=600)]

    @model_validator(mode="after")
    def _check_summary(self) -> "ReferenceClassSummary":
        if sum(self.by_outcome.values()) != self.total_comparables:
            raise ValueError("by_outcome counts must sum to total_comparables")
        grouped = {
            OutcomePolarity.CONTINUED: 0,
            OutcomePolarity.ENDED: 0,
            OutcomePolarity.UNCLEAR: 0,
        }
        for outcome, count in self.by_outcome.items():
            grouped[POLARITY_BY_OUTCOME[outcome]] += count
        if self.continued_count != grouped[OutcomePolarity.CONTINUED]:
            raise ValueError("continued_count must match by_outcome grouped by polarity")
        if self.ended_count != grouped[OutcomePolarity.ENDED]:
            raise ValueError("ended_count must match by_outcome grouped by polarity")
        if self.unclear_count != grouped[OutcomePolarity.UNCLEAR]:
            raise ValueError("unclear_count must match by_outcome grouped by polarity")
        _reject_forbidden(self.narrative)
        return self


class IdeaProfile(BaseModel):
    """Coarse, deterministic keyword-derived reading of a startup idea.

    Every field is best-effort. Unresolvable fields fall back to a sentinel
    (``"unspecified"`` / ``*.UNKNOWN``) and are listed in ``unresolved_fields``;
    downstream code must treat those neutrally, never as a mismatch. See
    :mod:`services.idea_profile` for the derivation rules and their documented
    limitations.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    raw_text: Annotated[str, Field(min_length=1, max_length=10_000)]
    customer_type: CustomerType = CustomerType.UNKNOWN
    customer_descriptor: Annotated[str, Field(min_length=1, max_length=120)] = "unspecified"
    problem: Annotated[str, Field(min_length=1, max_length=300)] = "unspecified"
    product_form: ProductForm = ProductForm.UNKNOWN
    business_model: BusinessModel = BusinessModel.UNKNOWN
    industry: Annotated[str, Field(min_length=1, max_length=40)] = "unspecified"
    geography: Annotated[str, Field(min_length=1, max_length=60)] = "unspecified"
    keywords: list[
        Annotated[
            str,
            Field(
                min_length=1,
                max_length=40,
                pattern=r"^[a-z0-9][a-z0-9.+\-]*( [a-z0-9][a-z0-9.+\-]*)?$",
            ),
        ]
    ] = Field(default_factory=list, max_length=20)
    unresolved_fields: list[UnresolvedField] = Field(default_factory=list, max_length=7)

    @model_validator(mode="after")
    def _check_keywords_unique(self) -> "IdeaProfile":
        if len(set(self.keywords)) != len(self.keywords):
            raise ValueError("keywords must not contain duplicates")
        return self

    @model_validator(mode="after")
    def _check_unresolved_fields_order(self) -> "IdeaProfile":
        if len(set(self.unresolved_fields)) != len(self.unresolved_fields):
            raise ValueError("unresolved_fields must not contain duplicates")
        marked = set(self.unresolved_fields)
        canonical = [f for f in UNRESOLVED_FIELD_ORDER if f in marked]
        if list(self.unresolved_fields) != canonical:
            raise ValueError("unresolved_fields must be in canonical order")
        return self

    @model_validator(mode="after")
    def _check_resolution_consistency(self) -> "IdeaProfile":
        marked = set(self.unresolved_fields)
        pairs = (
            (self.customer_type is CustomerType.UNKNOWN, UnresolvedField.CUSTOMER_TYPE),
            (self.customer_descriptor == "unspecified", UnresolvedField.CUSTOMER_DESCRIPTOR),
            (self.problem == "unspecified", UnresolvedField.PROBLEM),
            (self.product_form is ProductForm.UNKNOWN, UnresolvedField.PRODUCT_FORM),
            (self.business_model is BusinessModel.UNKNOWN, UnresolvedField.BUSINESS_MODEL),
            (self.industry == "unspecified", UnresolvedField.INDUSTRY),
            (self.geography == "unspecified", UnresolvedField.GEOGRAPHY),
        )
        for is_unresolved, field in pairs:
            if is_unresolved != (field in marked):
                raise ValueError(
                    f"{field.value}: sentinel value and membership in "
                    f"unresolved_fields must agree"
                )
        return self


class CandidateProfile(BaseModel):
    """Structured attributes of one discovered candidate startup (input to 4B).

    Produced by 4C from discovery / verification evidence and consumed by
    :func:`services.similarity.score_similarity`. Field names and types are a
    strict subset of :class:`VerifiedCandidate`, so 4C can assemble a
    ``VerifiedCandidate`` from a ``CandidateProfile`` plus the resulting
    ``SimilarityBreakdown``. Carries no evidence ids and no verification state --
    similarity is computed from structured attributes only.
    """

    model_config = ConfigDict(extra="forbid", strict=True)

    name: Annotated[str, Field(min_length=1, max_length=120)]
    one_liner: Annotated[str, Field(min_length=1, max_length=200)]
    industry: Annotated[str, Field(min_length=1, max_length=40)] = "unspecified"
    geography: Annotated[str, Field(min_length=1, max_length=60)] | None = None
    business_model: BusinessModel = BusinessModel.UNKNOWN
    product_form: ProductForm = ProductForm.UNKNOWN
    customer_type: CustomerType = CustomerType.UNKNOWN
    customer_descriptor: Annotated[str, Field(min_length=1, max_length=120)] | None = None


class ReferenceClass(BaseModel):
    # Holds a plain EvidenceStore (not a pydantic model), like services.research.ResearchRun.
    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    idea_profile: IdeaProfile
    status: ReferenceClassStatus
    comparables: list[ComparableStartup] = Field(
        default_factory=list, max_length=MAX_COMPARABLES
    )
    dropped_candidates: list[DroppedCandidate] = Field(default_factory=list)
    patterns: list[ReferenceClassPattern] = Field(
        default_factory=list, max_length=MAX_PATTERNS
    )
    summary: ReferenceClassSummary
    disclaimer: str = REFERENCE_CLASS_DISCLAIMER
    discovery_search_count: Annotated[int, Field(ge=0, le=MAX_DISCOVERY_QUERIES)]
    verification_search_count: Annotated[int, Field(ge=0, le=MAX_VERIFICATION_SEARCHES)]
    # Step-4 invariant: 0. Kept as a plain ge=0 field (not le=0) so 4G can relax
    # it without a schema change; the invariant is asserted by tests.
    llm_calls: Annotated[int, Field(ge=0)] = 0
    evidence_store: EvidenceStore

    @model_validator(mode="after")
    def _check_reference_class(self) -> "ReferenceClass":
        if self.summary.total_comparables != len(self.comparables):
            raise ValueError("summary.total_comparables must equal len(comparables)")
        if self.summary.dropped_count != len(self.dropped_candidates):
            raise ValueError(
                "summary.dropped_count must equal len(dropped_candidates)"
            )

        observed: dict[StartupOutcome, int] = {}
        for c in self.comparables:
            observed[c.outcome.outcome] = observed.get(c.outcome.outcome, 0) + 1
        declared = {k: v for k, v in self.summary.by_outcome.items() if v}
        if declared != observed:
            raise ValueError(
                "summary.by_outcome must match comparables grouped by outcome"
            )

        # Traceability invariant #2: every comparable evidence id resolves.
        for c in self.comparables:
            for eid in c.evidence_ids:
                if self.evidence_store.get(eid) is None:
                    raise ValueError(
                        f"comparable {c.name!r} cites evidence id {eid} absent "
                        f"from the reference EvidenceStore"
                    )
        # Traceability invariant #4: every dropped-candidate evidence id resolves.
        for d in self.dropped_candidates:
            for eid in d.evidence_ids:
                if self.evidence_store.get(eid) is None:
                    raise ValueError(
                        f"dropped candidate {d.name!r} cites evidence id {eid} "
                        f"absent from the reference EvidenceStore"
                    )

        # Invariant #5: patterns may cite only included comparables.
        known_names = {c.name for c in self.comparables}
        known_names.update(a for c in self.comparables for a in c.aliases)
        for p in self.patterns:
            for name in p.supporting_startups:
                if name not in known_names:
                    raise ValueError(
                        f"pattern {p.id} cites startup {name!r} that is not an "
                        f"included comparable"
                    )
        pattern_ids = [p.id for p in self.patterns]
        if len(set(pattern_ids)) != len(pattern_ids):
            raise ValueError("pattern ids must be unique")

        # Status consistency -- only the structurally provable cases. PARTIAL is
        # an engine invariant and is intentionally not checked here.
        if self.status is ReferenceClassStatus.UNAVAILABLE_NO_PROVIDER:
            if self.comparables or self.patterns or self.dropped_candidates:
                raise ValueError(
                    "UNAVAILABLE_NO_PROVIDER implies no comparables, patterns, "
                    "or dropped candidates"
                )
            if self.discovery_search_count or self.verification_search_count:
                raise ValueError("UNAVAILABLE_NO_PROVIDER implies zero searches")
        if self.status is ReferenceClassStatus.UNAVAILABLE_NO_MATCHES:
            if self.comparables or self.patterns:
                raise ValueError(
                    "UNAVAILABLE_NO_MATCHES implies no comparables or patterns"
                )
        return self
