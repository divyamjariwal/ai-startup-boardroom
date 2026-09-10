"""4E -- reference-class aggregation (the final Step-4 engine).

Turn the 4D :class:`OutcomeVerificationResult` into the 4A
:class:`ReferenceClass`: order the comparables, count outcomes, write the
neutral summary via :func:`build_summary_narrative`, and **deterministically**
derive a few :class:`ReferenceClassPattern` observations by counting over
``ComparableStartup`` fields. No LLM, no network, no mutation, no randomness.

Every pattern is a bounded observation about *the retrieved sample*
("N of the M retrieved comparables ..."), never a population-level or
predictive claim; the 4A ``_reject_forbidden`` guard enforces the wording.
"""

from typing import NamedTuple

from models.reference_class import (
    MAX_DISCOVERY_QUERIES,
    MAX_PATTERNS,
    PATTERN_MEDIUM_CONFIDENCE_MIN_SUPPORT,
    PATTERN_MIN_SUPPORT,
    POLARITY_BY_OUTCOME,
    ComparableFlag,
    ComparableStartup,
    OutcomePolarity,
    PatternConfidence,
    PatternType,
    ReferenceClass,
    ReferenceClassPattern,
    ReferenceClassSummary,
    StartupOutcome,
    build_summary_narrative,
)
from services.reference_outcomes import OutcomeVerificationResult

# A pattern reaches MEDIUM confidence only when it is well-supported *and* covers
# a majority of the retrieved comparables; otherwise LOW.
_PATTERN_MAJORITY = 0.5

# "Continued"-style outcomes get an OUTCOME_TENDENCY pattern. SHUT_DOWN ->
# RECURRING_RISK, PIVOTED -> COMMON_PIVOT (handled separately), UNKNOWN -> none.
_OUTCOME_TENDENCY_PHRASES: dict[StartupOutcome, str] = {
    StartupOutcome.ACQUIRED: "were acquired by another company",
    StartupOutcome.PUBLIC: "went public",
    StartupOutcome.ACTIVE: "were still operating as of their most recent retrieved source",
}

# (attribute on ComparableStartup, linked_assumption_hint, sentence template)
_GTM_ATTRIBUTES: tuple[tuple[str, str, str], ...] = (
    ("business_model", "business_model", "use a {value} business model"),
    ("product_form", "product_form", "are built as {value} products"),
    ("customer_type", "customer", "target {value} customers"),
    ("industry", "market", "operate in {value}"),
)
_GTM_SENTINELS = frozenset({"unknown", "unspecified"})


class _PatternDraft(NamedTuple):
    pattern_type: PatternType
    text: str
    supporting: list[str]
    hint: str | None


def _year_span(comparables: list[ComparableStartup]) -> str:
    years = sorted(
        c.outcome.outcome_year for c in comparables if c.outcome.outcome_year is not None
    )
    if not years:
        return ""
    if years[0] == years[-1]:
        return f" ({years[0]})"
    return f" ({years[0]}-{years[-1]})"


def _derive_patterns(comparables: list[ComparableStartup]) -> list[ReferenceClassPattern]:
    total = len(comparables)
    if total < PATTERN_MIN_SUPPORT:
        return []

    by_outcome: dict[StartupOutcome, list[ComparableStartup]] = {}
    for comparable in comparables:
        by_outcome.setdefault(comparable.outcome.outcome, []).append(comparable)

    drafts: list[_PatternDraft] = []

    # A. continued-style outcome tendencies
    for outcome in (StartupOutcome.ACQUIRED, StartupOutcome.PUBLIC, StartupOutcome.ACTIVE):
        group = by_outcome.get(outcome, [])
        if len(group) >= PATTERN_MIN_SUPPORT:
            drafts.append(
                _PatternDraft(
                    PatternType.OUTCOME_TENDENCY,
                    f"{len(group)} of the {total} retrieved comparables "
                    f"{_OUTCOME_TENDENCY_PHRASES[outcome]}{_year_span(group)}.",
                    [c.name for c in group],
                    None,
                )
            )

    # B. ended outcomes -> recurring risk
    shut = by_outcome.get(StartupOutcome.SHUT_DOWN, [])
    if len(shut) >= PATTERN_MIN_SUPPORT:
        drafts.append(
            _PatternDraft(
                PatternType.RECURRING_RISK,
                f"{len(shut)} of the {total} retrieved comparables shut down"
                f"{_year_span(shut)}.",
                [c.name for c in shut],
                None,
            )
        )

    # C. common pivot
    pivoted = by_outcome.get(StartupOutcome.PIVOTED, [])
    if len(pivoted) >= PATTERN_MIN_SUPPORT:
        drafts.append(
            _PatternDraft(
                PatternType.COMMON_PIVOT,
                f"{len(pivoted)} of the {total} retrieved comparables pivoted away "
                f"from their original product or market{_year_span(pivoted)}.",
                [c.name for c in pivoted],
                None,
            )
        )

    # D. conflicting outcome reports -> data-quality risk
    conflicted = [c for c in comparables if ComparableFlag.CONFLICTING_OUTCOME in c.flags]
    if len(conflicted) >= PATTERN_MIN_SUPPORT:
        drafts.append(
            _PatternDraft(
                PatternType.RECURRING_RISK,
                f"{len(conflicted)} of the {total} retrieved comparables have "
                f"conflicting outcome reports across the retrieved sources.",
                [c.name for c in conflicted],
                None,
            )
        )

    # E. structural / go-to-market clustering (dominant value per attribute)
    for attribute, hint, template in _GTM_ATTRIBUTES:
        groups: dict[str, list[ComparableStartup]] = {}
        for comparable in comparables:
            raw = getattr(comparable, attribute)
            token = raw.value if hasattr(raw, "value") else raw
            if token is None or token in _GTM_SENTINELS:
                continue
            groups.setdefault(token, []).append(comparable)
        if not groups:
            continue
        token, group = min(groups.items(), key=lambda kv: (-len(kv[1]), kv[0]))
        # GTM patterns must describe a *majority* value, not incidental trivia.
        if len(group) >= PATTERN_MIN_SUPPORT and len(group) >= _PATTERN_MAJORITY * total:
            drafts.append(
                _PatternDraft(
                    PatternType.GTM_PATTERN,
                    f"{len(group)} of the {total} retrieved comparables "
                    f"{template.format(value=token.replace('_', ' '))}.",
                    [c.name for c in group],
                    hint,
                )
            )

    valid = [d for d in drafts if len(set(d.supporting)) >= PATTERN_MIN_SUPPORT]
    patterns: list[ReferenceClassPattern] = []
    for index, draft in enumerate(valid[:MAX_PATTERNS], start=1):
        supporting = list(dict.fromkeys(draft.supporting))
        support_count = len(supporting)
        confidence = (
            PatternConfidence.MEDIUM
            if support_count >= PATTERN_MEDIUM_CONFIDENCE_MIN_SUPPORT
            and support_count >= _PATTERN_MAJORITY * total
            else PatternConfidence.LOW
        )
        patterns.append(
            ReferenceClassPattern(
                id=f"RCP-{index:02d}",
                text=draft.text[:400],
                pattern_type=draft.pattern_type,
                supporting_startups=supporting,
                support_count=support_count,
                confidence=confidence,
                linked_assumption_hint=draft.hint,
            )
        )
    return patterns


def build_reference_class(verification: OutcomeVerificationResult) -> ReferenceClass:
    """Assemble the final 4A ``ReferenceClass`` from a 4D verification result."""

    comparables = sorted(
        verification.comparables,
        key=lambda c: (
            -c.similarity.total,
            -c.outcome.confidence,
            -len(c.evidence_ids),
            c.name,
        ),
    )
    total = len(comparables)

    by_outcome: dict[StartupOutcome, int] = {}
    for comparable in comparables:
        by_outcome[comparable.outcome.outcome] = (
            by_outcome.get(comparable.outcome.outcome, 0) + 1
        )
    continued = sum(
        n for o, n in by_outcome.items() if POLARITY_BY_OUTCOME[o] is OutcomePolarity.CONTINUED
    )
    ended = sum(
        n for o, n in by_outcome.items() if POLARITY_BY_OUTCOME[o] is OutcomePolarity.ENDED
    )
    unclear = sum(
        n for o, n in by_outcome.items() if POLARITY_BY_OUTCOME[o] is OutcomePolarity.UNCLEAR
    )
    dropped = list(verification.dropped)

    summary = ReferenceClassSummary(
        total_comparables=total,
        by_outcome=by_outcome,
        continued_count=continued,
        ended_count=ended,
        unclear_count=unclear,
        dropped_count=len(dropped),
        narrative=build_summary_narrative(
            total_comparables=total,
            continued_count=continued,
            ended_count=ended,
            unclear_count=unclear,
            dropped_count=len(dropped),
        ),
    )

    return ReferenceClass(
        idea_profile=verification.idea_profile,
        status=verification.status,
        comparables=comparables,
        dropped_candidates=dropped,
        patterns=_derive_patterns(comparables),
        summary=summary,
        discovery_search_count=min(verification.search_count, MAX_DISCOVERY_QUERIES),
        verification_search_count=0,
        llm_calls=verification.llm_calls,
        evidence_store=verification.evidence_store,
    )
