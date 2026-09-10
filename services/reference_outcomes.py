"""4D -- deterministic outcome verification for discovered comparable startups.

Given the 4C :class:`DiscoveryResult` (a list of ``VerifiedCandidate`` + a
reference ``EvidenceStore``), decide, per candidate, *what appears to have
happened to it* -- ``ACTIVE`` / ``ACQUIRED`` / ``PUBLIC`` / ``SHUT_DOWN`` /
``PIVOTED`` / ``UNKNOWN`` -- purely from signal phrases found in the retrieved
evidence excerpts, and emit a 4A ``OutcomeAssessment`` + a ``ComparableStartup``.

Conservative, in the mould of :mod:`services.verifier`:

* No LLM, no network, no randomness, no mutation of inputs.
* An outcome is only asserted when a signal phrase appears in at least one
  ``MEDIUM``+ quality source. A bare homepage / directory / social page with no
  signal phrase is ``UNKNOWN`` -- "has a website" is never evidence of ``ACTIVE``.
* A terminal signal (``ACQUIRED`` / ``PUBLIC`` / ``SHUT_DOWN``) outranks
  ``PIVOTED``, which outranks ``ACTIVE``.
* ``ACTIVE`` requires a recent (<= ``ACTIVE_SIGNAL_RECENCY_MONTHS``) dated signal
  from a ``MEDIUM``+ source; an old funding mention decays to ``UNKNOWN``.
* Conflicting terminal signals are resolved to the most recent by parsed year;
  if that cannot be resolved the outcome is ``UNKNOWN`` and ``conflicting`` is set.
* ``UNKNOWN`` confidence is pinned low (<= ``OUTCOME_UNKNOWN_MAX_CONFIDENCE``).

4D does NOT aggregate patterns and does NOT build a ``ReferenceClass`` -- that
is 4E.
"""

import re
from datetime import date
from typing import Annotated, NamedTuple

from pydantic import BaseModel, ConfigDict, Field, model_validator

from models.evidence import Evidence, SourceQuality
from models.reference_class import (
    ACTIVE_SIGNAL_RECENCY_MONTHS,
    EARLIEST_PLAUSIBLE_YEAR,
    POLARITY_BY_OUTCOME,
    ComparableFlag,
    ComparableStartup,
    DroppedCandidate,
    IdeaProfile,
    OutcomeAssessment,
    OutcomePolarity,
    OutcomeSignal,
    ReferenceClassStatus,
    StartupOutcome,
    VerifiedCandidate,
)
from services.evidence_store import EvidenceStore
from services.reference_discovery import DiscoveryResult
from services.verifier import QUALITY_WEIGHT

# MEDIUM or better -- the bar for asserting a concrete outcome (mirrors verifier).
_STRONG_QUALITY_MIN = QUALITY_WEIGHT[SourceQuality.MEDIUM]

# Lowercase substring signal phrases. Checked against "<title>\n<excerpt>".
_ACQUIRED_PHRASES: tuple[str, ...] = (
    "acquired by", "was acquired", "has acquired", "to acquire", "acquisition of",
    "acqui-hire", "acquihire", "bought by", "purchased by", "taken over by",
    "takeover of", "merged with", "merger with", "snapped up by",
)
_PUBLIC_PHRASES: tuple[str, ...] = (
    "ipo", "initial public offering", "went public", "going public",
    "direct listing", "began trading", "started trading publicly", "(nasdaq:",
    "(nyse:", "listed on the nasdaq", "listed on the nyse", "via a spac",
    "spac merger",
)
_SHUT_DOWN_PHRASES: tuple[str, ...] = (
    "shut down", "shutting down", "shuts down", "wind down", "winding down",
    "wound down", "ceased operations", "cease operations", "ceasing operations",
    "closed its doors", "closing its doors", "has closed down", "is closing down",
    "filed for bankruptcy", "declared bankruptcy", "went bankrupt", "chapter 7",
    "chapter 11", "insolvency", "liquidation", "is now defunct", "no longer operating",
    "no longer in business", "went out of business", "laid off all", "shuttered",
    "dead pool", "deadpool",
)
_PIVOTED_PHRASES: tuple[str, ...] = (
    "pivoted", "pivoted to", "pivoted from", "pivoted away", "made a pivot",
    "rebranded as", "rebranded to", "relaunched as", "changed its focus",
    "shifted its focus", "now focuses on", "repositioned as", "changed direction to",
)
_ACTIVE_PHRASES: tuple[str, ...] = (
    "raised a", "raised $", "raises $", "raised €", "raised £", "series a",
    "series b", "series c", "series d", "series e", "series f", "seed round",
    "seed funding", "announced funding", "closed a funding round", "fresh funding",
    "new funding round", "currently operates", "is operational", "continues to operate",
    "today announced", "recently launched",
)

_PHRASES_BY_OUTCOME: tuple[tuple[StartupOutcome, tuple[str, ...]], ...] = (
    (StartupOutcome.ACQUIRED, _ACQUIRED_PHRASES),
    (StartupOutcome.PUBLIC, _PUBLIC_PHRASES),
    (StartupOutcome.SHUT_DOWN, _SHUT_DOWN_PHRASES),
    (StartupOutcome.PIVOTED, _PIVOTED_PHRASES),
    (StartupOutcome.ACTIVE, _ACTIVE_PHRASES),
)
_TERMINAL_OUTCOMES = frozenset(
    {StartupOutcome.ACQUIRED, StartupOutcome.PUBLIC, StartupOutcome.SHUT_DOWN}
)

_YEAR_RE = re.compile(r"\b(19[89]\d|20\d{2})\b")
_YEAR_WINDOW = 80


class _RawSignal(NamedTuple):
    outcome: StartupOutcome
    phrase: str
    evidence_id: str
    quality: SourceQuality
    year: int | None


# --------------------------------------------------------------------------- #
# Signal collection
# --------------------------------------------------------------------------- #
def _is_strong(quality: SourceQuality) -> bool:
    return QUALITY_WEIGHT[quality] >= _STRONG_QUALITY_MIN


def _year_near(text: str, pos: int, phrase_len: int) -> int | None:
    window = text[max(0, pos - _YEAR_WINDOW) : pos + phrase_len + _YEAR_WINDOW]
    ceiling = date.today().year + 1
    for match in _YEAR_RE.findall(window):
        year = int(match)
        if EARLIEST_PLAUSIBLE_YEAR <= year <= ceiling:
            return year
    return None


def _collect_signals(evidence: list[Evidence]) -> list[_RawSignal]:
    """At most one signal per (evidence item, outcome). Deterministic order."""

    signals: list[_RawSignal] = []
    for item in evidence:
        text = f"{item.title}\n{item.excerpt}".lower()
        for outcome, phrases in _PHRASES_BY_OUTCOME:
            for phrase in phrases:
                pos = text.find(phrase)
                if pos != -1:
                    signals.append(
                        _RawSignal(
                            outcome=outcome,
                            phrase=phrase,
                            evidence_id=item.evidence_id,
                            quality=item.source_quality,
                            year=_year_near(text, pos, len(phrase)),
                        )
                    )
                    break
    return signals


# --------------------------------------------------------------------------- #
# Assessment builders
# --------------------------------------------------------------------------- #
def _confidence(winners: list[_RawSignal], conflicting: bool) -> float:
    n_sources = len({s.evidence_id for s in winners})
    best_weight = max(QUALITY_WEIGHT[s.quality] for s in winners)  # 0.3 .. 0.9
    source_factor = 0.5 + 0.5 * min(n_sources / 2, 1.0)  # 1 src -> 0.75, 2+ -> 1.0
    recency_factor = 1.0 if any(s.year is not None for s in winners) else 0.7
    score = best_weight * source_factor * recency_factor
    if conflicting:
        score *= 0.6
    return round(min(score, 0.95), 2)


def _outcome_label(outcome: StartupOutcome) -> str:
    return outcome.value.upper().replace("_", " ")


def _to_signals(raw: list[_RawSignal]) -> list[OutcomeSignal]:
    return [
        OutcomeSignal(
            outcome=s.outcome,
            phrase=s.phrase[:120],
            evidence_id=s.evidence_id,
            source_quality=s.quality,
            detected_year=s.year,
        )
        for s in raw
    ]


def _rationale(
    outcome: StartupOutcome,
    winners: list[_RawSignal],
    all_signals: list[_RawSignal],
    conflicting: bool,
    outcome_year: int | None,
) -> str:
    n_sources = len({s.evidence_id for s in winners})
    best_quality = max((s.quality for s in winners), key=lambda q: QUALITY_WEIGHT[q])
    parts = [
        f"Classified {_outcome_label(outcome)}: {n_sources} source(s) "
        f"(strongest quality {best_quality.value}) "
        f"{'report' if n_sources != 1 else 'reports'} \"{winners[0].phrase}\""
        f"{f' ({outcome_year})' if outcome_year else ''}."
    ]
    if conflicting:
        parts.append("Differing terminal signals were resolved to the most recent by year.")
    other = sorted(
        {_outcome_label(s.outcome) for s in all_signals} - {_outcome_label(outcome)}
    )
    if other:
        parts.append(f"Other unused signal(s): {', '.join(other)}.")
    return " ".join(parts)[:600]


def _unknown_rationale(all_signals: list[_RawSignal], reason: str) -> str:
    if not all_signals:
        return (
            "No outcome signal (acquisition, IPO, shutdown, pivot, or recent "
            "funding) was found in the retrieved evidence; outcome treated as unknown."
        )
    seen = ", ".join(sorted({_outcome_label(s.outcome) for s in all_signals}))
    return (f"Outcome mentions ({seen}) were found but {reason}; outcome treated as unknown.")[
        :600
    ]


def _assess(
    outcome: StartupOutcome,
    winners: list[_RawSignal],
    all_signals: list[_RawSignal],
    conflicting: bool,
) -> OutcomeAssessment:
    supporting_ids = list(dict.fromkeys(s.evidence_id for s in winners))
    years = [s.year for s in winners if s.year is not None]
    outcome_year = max(years) if years else None
    return OutcomeAssessment(
        outcome=outcome,
        polarity=POLARITY_BY_OUTCOME[outcome],
        outcome_year=outcome_year,
        confidence=_confidence(winners, conflicting),
        supporting_evidence_ids=supporting_ids,
        signals=_to_signals(winners),
        rationale=_rationale(outcome, winners, all_signals, conflicting, outcome_year),
        conflicting=conflicting,
    )


def _unknown(
    all_signals: list[_RawSignal], reason: str, *, conflicting: bool = False
) -> OutcomeAssessment:
    return OutcomeAssessment(
        outcome=StartupOutcome.UNKNOWN,
        polarity=OutcomePolarity.UNCLEAR,
        outcome_year=None,
        confidence=0.1,
        supporting_evidence_ids=[],
        signals=_to_signals(all_signals),
        rationale=_unknown_rationale(all_signals, reason),
        conflicting=conflicting,
    )


# --------------------------------------------------------------------------- #
# Public: classify one candidate's evidence
# --------------------------------------------------------------------------- #
def classify_outcome(evidence: list[Evidence]) -> OutcomeAssessment:
    """Deterministically classify a startup's outcome from its evidence excerpts."""

    signals = _collect_signals(evidence)
    terminal = [s for s in signals if s.outcome in _TERMINAL_OUTCOMES]
    pivots = [s for s in signals if s.outcome is StartupOutcome.PIVOTED]
    actives = [s for s in signals if s.outcome is StartupOutcome.ACTIVE]

    if terminal:
        strong = [s for s in terminal if _is_strong(s.quality)]
        if not strong:
            return _unknown(signals, "appeared only in low-quality sources")
        strong_outcomes = {s.outcome for s in strong}
        if len(strong_outcomes) == 1:
            outcome = next(iter(strong_outcomes))
            return _assess(
                outcome, [s for s in strong if s.outcome is outcome], signals, conflicting=False
            )
        dated = [s for s in strong if s.year is not None]
        if dated:
            newest_year = max(s.year for s in dated)
            newest_outcomes = {s.outcome for s in dated if s.year == newest_year}
            if len(newest_outcomes) == 1:
                outcome = next(iter(newest_outcomes))
                return _assess(
                    outcome, [s for s in strong if s.outcome is outcome], signals, conflicting=True
                )
        return _unknown(
            signals, "could not be resolved to a single outcome by date", conflicting=True
        )

    if pivots:
        strong_pivots = [s for s in pivots if _is_strong(s.quality)]
        if strong_pivots:
            return _assess(StartupOutcome.PIVOTED, strong_pivots, signals, conflicting=False)

    if actives:
        recent_year = date.today().year - (ACTIVE_SIGNAL_RECENCY_MONTHS // 12)
        recent_strong = [
            s
            for s in actives
            if _is_strong(s.quality) and s.year is not None and s.year >= recent_year
        ]
        if recent_strong:
            return _assess(StartupOutcome.ACTIVE, recent_strong, signals, conflicting=False)
        return _unknown(
            signals, "were not recent enough to confirm the company is still active"
        )

    return _unknown(signals, "did not meet the evidence bar")


# --------------------------------------------------------------------------- #
# Public: classify a whole DiscoveryResult
# --------------------------------------------------------------------------- #
class OutcomeVerificationResult(BaseModel):
    """4D output. Mirrors :class:`DiscoveryResult` but with outcome-classified
    ``ComparableStartup`` objects instead of ``VerifiedCandidate`` objects."""

    model_config = ConfigDict(arbitrary_types_allowed=True, extra="forbid")

    idea_profile: IdeaProfile
    status: ReferenceClassStatus
    comparables: list[ComparableStartup] = Field(default_factory=list)
    dropped: list[DroppedCandidate] = Field(default_factory=list)
    evidence_store: EvidenceStore
    message: str
    # Passed through from the 4C DiscoveryResult so 4E has a complete input.
    search_count: Annotated[int, Field(ge=0)] = 0
    llm_calls: Annotated[int, Field(ge=0)] = 0

    @model_validator(mode="after")
    def _check_traceable(self) -> "OutcomeVerificationResult":
        for comparable in self.comparables:
            cited = list(comparable.evidence_ids) + list(
                comparable.outcome.supporting_evidence_ids
            )
            for evidence_id in cited:
                if self.evidence_store.get(evidence_id) is None:
                    raise ValueError(
                        f"comparable {comparable.name!r} cites evidence id "
                        f"{evidence_id} absent from the evidence store"
                    )
        return self


def _flags_for(
    candidate: VerifiedCandidate,
    assessment: OutcomeAssessment,
    evidence: list[Evidence],
) -> list[ComparableFlag]:
    flags = list(candidate.flags)

    def add(flag: ComparableFlag) -> None:
        if flag not in flags:
            flags.append(flag)

    if assessment.conflicting:
        add(ComparableFlag.CONFLICTING_OUTCOME)
    if assessment.outcome is StartupOutcome.PIVOTED:
        add(ComparableFlag.PIVOT)
    if len(candidate.evidence_ids) == 1:
        add(ComparableFlag.SINGLE_SOURCE)
    if evidence and all(not _is_strong(item.source_quality) for item in evidence):
        add(ComparableFlag.WEAK_SOURCES)
    return flags


def verify_outcomes(discovery: DiscoveryResult) -> OutcomeVerificationResult:
    """Classify every discovered candidate's outcome -> ``ComparableStartup`` list."""

    comparables: list[ComparableStartup] = []
    counts: dict[StartupOutcome, int] = {}

    for candidate in discovery.candidates:
        evidence = [
            item
            for eid in candidate.evidence_ids
            if (item := discovery.evidence_store.get(eid)) is not None
        ]
        assessment = classify_outcome(evidence)
        counts[assessment.outcome] = counts.get(assessment.outcome, 0) + 1

        comparables.append(
            ComparableStartup(
                name=candidate.name,
                aliases=list(candidate.aliases),
                one_liner=candidate.one_liner,
                industry=candidate.industry,
                geography=candidate.geography,
                business_model=candidate.business_model,
                product_form=candidate.product_form,
                customer_type=candidate.customer_type,
                customer_descriptor=candidate.customer_descriptor,
                founding_year=candidate.founding_year,
                similarity=candidate.similarity,
                evidence_ids=list(candidate.evidence_ids),
                is_company_verified=candidate.is_company_verified,
                is_relevant=candidate.is_relevant,
                flags=_flags_for(candidate, assessment, evidence),
                outcome=assessment,
            )
        )

    if comparables:
        summary = ", ".join(
            f"{count} {outcome.value}"
            for outcome, count in sorted(counts.items(), key=lambda kv: kv[0].value)
        )
        message = f"{len(comparables)} comparable startup(s) classified: {summary}."
    else:
        message = discovery.message

    return OutcomeVerificationResult(
        idea_profile=discovery.idea_profile,
        status=discovery.status,
        comparables=comparables,
        dropped=list(discovery.dropped),
        evidence_store=discovery.evidence_store,
        message=message,
        search_count=discovery.search_count,
        llm_calls=discovery.llm_calls,
    )
