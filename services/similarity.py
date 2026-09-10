"""4B -- deterministic reference-class similarity engine.

Given the founder's :class:`IdeaProfile` (4A) and a :class:`CandidateProfile`
(the structured attributes of one discovered startup), produce a 4A
:class:`SimilarityBreakdown`: six explainable per-dimension scores, a weighted
0-100 total, matched / divergent dimensions, and a plain-language rationale.

Pure and deterministic: no network, no LLM, no ``EvidenceStore`` access, no
mutation, no randomness. Identical inputs always produce an identical
``SimilarityBreakdown``.

Scoring
-------
The discrete band *values* per dimension come from the approved A/B
specification (design section 4):

* PROBLEM         keyword overlap of idea vocabulary vs. candidate one-liner
* CUSTOMER        exact segment 1.0 / same broad segment 0.5 / unknown 0.3 / conflicting 0.0
* INDUSTRY        exact tag 1.0 / sibling 0.5 / unrelated 0.0
* PRODUCT_FORM    exact 1.0 / adjacent 0.5 / mismatch 0.1
* BUSINESS_MODEL  exact 1.0 / related 0.6 / mismatch 0.1
* GEOGRAPHY       same 1.0 / both global 0.7 / unspecified 0.5 / different 0.3

Sentinels (``"unspecified"`` / ``*.UNKNOWN``) score ``UNKNOWN_DIMENSION_SCORE``
(0.30) on every dimension *except* GEOGRAPHY, where the spec fixes an
unspecified score of 0.50.

4B policy (the specification is silent on these)
----------------------------------------------
* the exact overlap-to-score bands for PROBLEM,
* which industry tags count as siblings (``_INDUSTRY_SIBLINGS``),
* which product forms count as adjacent (``_PRODUCT_FORM_ADJACENCY``),
* which business models count as related (``_BUSINESS_MODEL_RELATED``),
* the score for "one side global, the other a specific region".

These are the named constants / tables below. They are deterministic and
symmetric. They are NOT part of the original specification.

Weights are read from ``models.reference_class.SIMILARITY_WEIGHTS`` and are not
duplicated. Per-dimension weighted scores are stored raw (``score * weight``,
unrounded); only the final ``total`` is rounded, by the aggregation rule the 4A
``SimilarityBreakdown`` validator enforces: ``round(100 * sum(weighted))``.
"""

from collections.abc import Callable

from models.reference_class import (
    SIMILARITY_INCLUSION_THRESHOLD,
    SIMILARITY_MATCH_THRESHOLD,
    SIMILARITY_DIVERGENT_THRESHOLD,
    SIMILARITY_WEIGHTS,
    UNKNOWN_DIMENSION_SCORE,
    BusinessModel,
    CandidateProfile,
    CustomerType,
    DimensionScore,
    IdeaProfile,
    ProductForm,
    SimilarityBreakdown,
    SimilarityDimension,
)
from services.idea_profile import PITCH_STOP_WORDS, tokenize

_BASIS_MAX = 200
_RATIONALE_MAX = 600

# --------------------------------------------------------------------------- #
# PROBLEM -- keyword overlap of idea vocabulary vs. candidate one-liner.
# Spec fixes the idea (overlap of terms); the overlap -> score bands are 4B policy.
# --------------------------------------------------------------------------- #
PROBLEM_MIN_TOKEN_LEN = 3
PROBLEM_MAX_TOKEN_LEN = 40  # matches services.idea_profile keyword content bound
PROBLEM_INSUFFICIENT_TEXT_SCORE = UNKNOWN_DIMENSION_SCORE  # 0.30
PROBLEM_ZERO_OVERLAP_SCORE = 0.10
PROBLEM_SMALL_OVERLAP_SCORE = 0.30  # 0 < overlap < first band threshold
# overlap = |idea_terms & candidate_terms| / |idea_terms|; highest threshold first.
PROBLEM_OVERLAP_BANDS: tuple[tuple[float, float], ...] = (
    (0.50, 1.00),
    (0.30, 0.70),
    (0.15, 0.50),
)

# --------------------------------------------------------------------------- #
# CUSTOMER -- spec: exact segment 1.0 / same broad 0.5 / unknown 0.3 / conflict 0.0.
# 4B policy: "different known types, neither is CONSUMER" -> related org buyers 0.30;
#            "different known types, exactly one is CONSUMER" -> conflicting 0.0.
# --------------------------------------------------------------------------- #
CUSTOMER_EXACT_SEGMENT_SCORE = 1.00
CUSTOMER_SAME_TYPE_SCORE = 0.50
CUSTOMER_RELATED_ORG_SCORE = UNKNOWN_DIMENSION_SCORE  # 0.30
CUSTOMER_CONFLICT_SCORE = 0.00

# --------------------------------------------------------------------------- #
# INDUSTRY -- spec: exact 1.0 / sibling 0.5 / unrelated 0.0.
# 4B policy: the sibling set. Every tag exists in services.idea_profile.INDUSTRY_TAGS
# (guarded by tests). Unordered pairs; membership test is frozenset({a, b}) in ....
# --------------------------------------------------------------------------- #
INDUSTRY_EXACT_SCORE = 1.00
INDUSTRY_SIBLING_SCORE = 0.50
INDUSTRY_UNRELATED_SCORE = 0.00
_INDUSTRY_SIBLINGS: frozenset[frozenset[str]] = frozenset(
    {
        frozenset({"fintech", "insurtech"}),
        frozenset({"healthtech", "biotech"}),
        frozenset({"devtools", "data_ai"}),
        frozenset({"devtools", "cybersecurity"}),
        frozenset({"data_ai", "cybersecurity"}),
        frozenset({"ecommerce", "logistics"}),
        frozenset({"logistics", "mobility"}),
        frozenset({"media", "social"}),
    }
)

# --------------------------------------------------------------------------- #
# PRODUCT_FORM -- spec: exact 1.0 / adjacent 0.5 / mismatch 0.1.
# 4B policy: the adjacency set (unordered pairs of real ProductForm members).
# --------------------------------------------------------------------------- #
PRODUCT_FORM_EXACT_SCORE = 1.00
PRODUCT_FORM_ADJACENT_SCORE = 0.50
PRODUCT_FORM_MISMATCH_SCORE = 0.10
_PRODUCT_FORM_ADJACENCY: frozenset[frozenset[ProductForm]] = frozenset(
    {
        frozenset({ProductForm.APP, ProductForm.SAAS}),
        frozenset({ProductForm.APP, ProductForm.PLATFORM}),
        frozenset({ProductForm.APP, ProductForm.CONTENT}),
        frozenset({ProductForm.SAAS, ProductForm.PLATFORM}),
        frozenset({ProductForm.SAAS, ProductForm.API}),
        frozenset({ProductForm.SAAS, ProductForm.SERVICE}),
        frozenset({ProductForm.API, ProductForm.PLATFORM}),
        frozenset({ProductForm.MARKETPLACE, ProductForm.PLATFORM}),
    }
)

# --------------------------------------------------------------------------- #
# BUSINESS_MODEL -- spec: exact 1.0 / related 0.6 / mismatch 0.1.
# 4B policy: the related set (unordered pairs of real BusinessModel members).
# --------------------------------------------------------------------------- #
BUSINESS_MODEL_EXACT_SCORE = 1.00
BUSINESS_MODEL_RELATED_SCORE = 0.60
BUSINESS_MODEL_MISMATCH_SCORE = 0.10
_BUSINESS_MODEL_RELATED: frozenset[frozenset[BusinessModel]] = frozenset(
    {
        frozenset({BusinessModel.SUBSCRIPTION, BusinessModel.FREEMIUM}),
        frozenset({BusinessModel.SUBSCRIPTION, BusinessModel.LICENSING}),
        frozenset({BusinessModel.TRANSACTIONAL, BusinessModel.MARKETPLACE}),
        frozenset({BusinessModel.ADVERTISING, BusinessModel.FREEMIUM}),
    }
)

# --------------------------------------------------------------------------- #
# GEOGRAPHY -- spec: same 1.0 / both global 0.7 / unspecified 0.5 / different 0.3.
# 4B policy: "one side global, the other a specific region" -> 0.50.
# Comparison is on the exact GEO_REGIONS label string from services.idea_profile.
# --------------------------------------------------------------------------- #
GEOGRAPHY_SAME_SCORE = 1.00
GEOGRAPHY_BOTH_GLOBAL_SCORE = 0.70
GEOGRAPHY_UNSPECIFIED_SCORE = 0.50
GEOGRAPHY_GLOBAL_VS_REGION_SCORE = 0.50
GEOGRAPHY_DIFFERENT_SCORE = 0.30
_GEO_UNSPECIFIED = "unspecified"
_GEO_GLOBAL = "Global"

_DIMENSION_LABELS: dict[SimilarityDimension, str] = {
    SimilarityDimension.PROBLEM: "problem",
    SimilarityDimension.CUSTOMER: "customer",
    SimilarityDimension.INDUSTRY: "industry",
    SimilarityDimension.PRODUCT_FORM: "product form",
    SimilarityDimension.BUSINESS_MODEL: "business model",
    SimilarityDimension.GEOGRAPHY: "geography",
}


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _content_tokens(text: str) -> set[str]:
    """Lowercase content tokens: shared tokeniser, minus pitch stop words and
    tokens outside the length band used for 4A keyword extraction."""

    return {
        token
        for token in tokenize(text)
        if token not in PITCH_STOP_WORDS
        and PROBLEM_MIN_TOKEN_LEN <= len(token) <= PROBLEM_MAX_TOKEN_LEN
        and not token.isdigit()
    }


def _which_side(idea_missing: bool, candidate_missing: bool) -> str:
    if idea_missing and candidate_missing:
        return "both sides"
    return "idea side" if idea_missing else "candidate side"


def _truncate(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[:limit]


# --------------------------------------------------------------------------- #
# Per-dimension scorers -- each returns (score in [0, 1], deterministic basis).
# --------------------------------------------------------------------------- #
def _score_problem(idea: IdeaProfile, candidate: CandidateProfile) -> tuple[float, str]:
    idea_terms: set[str] = set()
    for keyword in idea.keywords:
        idea_terms |= _content_tokens(keyword)
    if idea.problem != "unspecified":
        idea_terms |= _content_tokens(idea.problem)
    candidate_terms = _content_tokens(candidate.one_liner)

    if not idea_terms or not candidate_terms:
        return (
            PROBLEM_INSUFFICIENT_TEXT_SCORE,
            f"problem: insufficient text to compare (idea terms={len(idea_terms)}, "
            f"candidate terms={len(candidate_terms)})",
        )

    shared = idea_terms & candidate_terms
    overlap = len(shared) / len(idea_terms)
    if overlap == 0.0:
        score = PROBLEM_ZERO_OVERLAP_SCORE
    else:
        score = PROBLEM_SMALL_OVERLAP_SCORE
        for threshold, banded in PROBLEM_OVERLAP_BANDS:
            if overlap >= threshold:
                score = banded
                break
    return (
        score,
        f"problem: {len(shared)}/{len(idea_terms)} idea terms present in candidate "
        f"one-liner (overlap {overlap:.2f})",
    )


def _score_customer(idea: IdeaProfile, candidate: CandidateProfile) -> tuple[float, str]:
    idea_type = idea.customer_type
    candidate_type = candidate.customer_type

    if idea_type is CustomerType.UNKNOWN or candidate_type is CustomerType.UNKNOWN:
        return (
            UNKNOWN_DIMENSION_SCORE,
            "customer: type unknown on "
            + _which_side(
                idea_type is CustomerType.UNKNOWN,
                candidate_type is CustomerType.UNKNOWN,
            ),
        )

    if idea_type is candidate_type:
        idea_descriptor = (
            idea.customer_descriptor
            if idea.customer_descriptor != "unspecified"
            else None
        )
        candidate_descriptor = candidate.customer_descriptor
        if idea_descriptor and candidate_descriptor:
            shared = _content_tokens(idea_descriptor) & _content_tokens(candidate_descriptor)
            if shared:
                return (
                    CUSTOMER_EXACT_SEGMENT_SCORE,
                    f"customer: same segment '{idea_type.value}', descriptor overlap "
                    f"{{{', '.join(sorted(shared))}}}",
                )
        return (
            CUSTOMER_SAME_TYPE_SCORE,
            f"customer: same broad segment '{idea_type.value}', descriptors not aligned",
        )

    exactly_one_consumer = (idea_type is CustomerType.CONSUMER) != (
        candidate_type is CustomerType.CONSUMER
    )
    if exactly_one_consumer:
        return (
            CUSTOMER_CONFLICT_SCORE,
            f"customer: conflicting segments (idea={idea_type.value}, "
            f"candidate={candidate_type.value})",
        )
    return (
        CUSTOMER_RELATED_ORG_SCORE,
        f"customer: related organisational buyers (idea={idea_type.value}, "
        f"candidate={candidate_type.value})",
    )


def _score_industry(idea: IdeaProfile, candidate: CandidateProfile) -> tuple[float, str]:
    idea_industry = idea.industry
    candidate_industry = candidate.industry
    if idea_industry == "unspecified" or candidate_industry == "unspecified":
        return (
            UNKNOWN_DIMENSION_SCORE,
            "industry: unspecified on "
            + _which_side(
                idea_industry == "unspecified", candidate_industry == "unspecified"
            ),
        )
    if idea_industry == candidate_industry:
        return (INDUSTRY_EXACT_SCORE, f"industry: exact tag match ({idea_industry})")
    if frozenset({idea_industry, candidate_industry}) in _INDUSTRY_SIBLINGS:
        return (
            INDUSTRY_SIBLING_SCORE,
            f"industry: related sectors ({idea_industry} / {candidate_industry})",
        )
    return (
        INDUSTRY_UNRELATED_SCORE,
        f"industry: unrelated (idea={idea_industry}, candidate={candidate_industry})",
    )


def _score_product_form(idea: IdeaProfile, candidate: CandidateProfile) -> tuple[float, str]:
    idea_form = idea.product_form
    candidate_form = candidate.product_form
    if idea_form is ProductForm.UNKNOWN or candidate_form is ProductForm.UNKNOWN:
        return (
            UNKNOWN_DIMENSION_SCORE,
            "product form: unknown on "
            + _which_side(
                idea_form is ProductForm.UNKNOWN,
                candidate_form is ProductForm.UNKNOWN,
            ),
        )
    if idea_form is candidate_form:
        return (PRODUCT_FORM_EXACT_SCORE, f"product form: exact match ({idea_form.value})")
    if frozenset({idea_form, candidate_form}) in _PRODUCT_FORM_ADJACENCY:
        return (
            PRODUCT_FORM_ADJACENT_SCORE,
            f"product form: adjacent forms ({idea_form.value} / {candidate_form.value})",
        )
    return (
        PRODUCT_FORM_MISMATCH_SCORE,
        f"product form: mismatch (idea={idea_form.value}, candidate={candidate_form.value})",
    )


def _score_business_model(idea: IdeaProfile, candidate: CandidateProfile) -> tuple[float, str]:
    idea_model = idea.business_model
    candidate_model = candidate.business_model
    if idea_model is BusinessModel.UNKNOWN or candidate_model is BusinessModel.UNKNOWN:
        return (
            UNKNOWN_DIMENSION_SCORE,
            "business model: unknown on "
            + _which_side(
                idea_model is BusinessModel.UNKNOWN,
                candidate_model is BusinessModel.UNKNOWN,
            ),
        )
    if idea_model is candidate_model:
        return (
            BUSINESS_MODEL_EXACT_SCORE,
            f"business model: exact match ({idea_model.value})",
        )
    if frozenset({idea_model, candidate_model}) in _BUSINESS_MODEL_RELATED:
        return (
            BUSINESS_MODEL_RELATED_SCORE,
            f"business model: related models ({idea_model.value} / {candidate_model.value})",
        )
    return (
        BUSINESS_MODEL_MISMATCH_SCORE,
        f"business model: mismatch (idea={idea_model.value}, candidate={candidate_model.value})",
    )


def _score_geography(idea: IdeaProfile, candidate: CandidateProfile) -> tuple[float, str]:
    idea_geo = idea.geography or _GEO_UNSPECIFIED
    candidate_geo = candidate.geography or _GEO_UNSPECIFIED

    if idea_geo == _GEO_GLOBAL and candidate_geo == _GEO_GLOBAL:
        return (GEOGRAPHY_BOTH_GLOBAL_SCORE, "geography: both global")
    if idea_geo == _GEO_UNSPECIFIED or candidate_geo == _GEO_UNSPECIFIED:
        return (
            GEOGRAPHY_UNSPECIFIED_SCORE,
            "geography: unspecified on "
            + _which_side(
                idea_geo == _GEO_UNSPECIFIED, candidate_geo == _GEO_UNSPECIFIED
            ),
        )
    if idea_geo == candidate_geo:
        return (GEOGRAPHY_SAME_SCORE, f"geography: same region ({idea_geo})")
    if idea_geo == _GEO_GLOBAL or candidate_geo == _GEO_GLOBAL:
        return (
            GEOGRAPHY_GLOBAL_VS_REGION_SCORE,
            f"geography: one global, one regional ({idea_geo} / {candidate_geo})",
        )
    return (
        GEOGRAPHY_DIFFERENT_SCORE,
        f"geography: different regions (idea={idea_geo}, candidate={candidate_geo})",
    )


_SCORERS: dict[
    SimilarityDimension, Callable[[IdeaProfile, CandidateProfile], tuple[float, str]]
] = {
    SimilarityDimension.PROBLEM: _score_problem,
    SimilarityDimension.CUSTOMER: _score_customer,
    SimilarityDimension.INDUSTRY: _score_industry,
    SimilarityDimension.PRODUCT_FORM: _score_product_form,
    SimilarityDimension.BUSINESS_MODEL: _score_business_model,
    SimilarityDimension.GEOGRAPHY: _score_geography,
}


def _build_rationale(
    total: int,
    matched: list[SimilarityDimension],
    divergent: list[SimilarityDimension],
) -> str:
    aligned = ", ".join(_DIMENSION_LABELS[d] for d in matched) if matched else "none"
    diverged = ", ".join(_DIMENSION_LABELS[d] for d in divergent) if divergent else "none"
    # The candidate name is intentionally excluded: a real company name containing
    # a FORBIDDEN_DESCRIPTIVE_PHRASES substring (e.g. "Guaranteed Rate") would
    # otherwise make the 4A SimilarityBreakdown validator reject this output.
    return (
        f"Candidate similarity {total}/100. "
        f"Aligned on: {aligned}. Divergent on: {diverged}. "
        f"Dimension weights -- problem 0.25, customer 0.20, industry 0.20, "
        f"product form 0.15, business model 0.15, geography 0.05."
    )


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def score_similarity(
    idea: IdeaProfile,
    candidate: CandidateProfile,
) -> SimilarityBreakdown:
    """Score one candidate startup against the founder's idea profile.

    Deterministic and side-effect free. Returns a fully validated
    :class:`SimilarityBreakdown` (the 4A model validators are the source of
    truth for output validity).
    """

    dimensions: list[DimensionScore] = []
    for dimension in SimilarityDimension:
        raw_score, basis = _SCORERS[dimension](idea, candidate)
        weight = SIMILARITY_WEIGHTS[dimension]
        dimensions.append(
            DimensionScore(
                dimension=dimension,
                score=raw_score,
                weight=weight,
                weighted_score=raw_score * weight,  # stored raw; only `total` is rounded
                basis=_truncate(basis, _BASIS_MAX),
            )
        )

    total = round(100 * sum(d.weighted_score for d in dimensions))
    matched = [d.dimension for d in dimensions if d.score >= SIMILARITY_MATCH_THRESHOLD]
    divergent = [
        d.dimension for d in dimensions if d.score <= SIMILARITY_DIVERGENT_THRESHOLD
    ]
    return SimilarityBreakdown(
        dimensions=dimensions,
        total=total,
        matched_dimensions=matched,
        divergent_dimensions=divergent,
        rationale=_truncate(_build_rationale(total, matched, divergent), _RATIONALE_MAX),
    )


def is_relevant(breakdown: SimilarityBreakdown) -> bool:
    """Whether a candidate clears the reference-class inclusion cut-off.

    The single definition of "relevant": the 4A ``VerifiedCandidate`` validator
    enforces the same ``similarity.total >= SIMILARITY_INCLUSION_THRESHOLD``.
    """

    return breakdown.total >= SIMILARITY_INCLUSION_THRESHOLD
