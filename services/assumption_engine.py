"""Deterministic ranking of the specialists' load-bearing assumptions.

Collects ``AssumptionDraft`` objects from the specialist ``AgentResult``s,
collapses exact (normalized) text duplicates, scores each by
``impact * uncertainty``, ranks them, and derives an evidence status from the
already-verified claims. No LLM calls, no fuzzy matching, no external state.
"""

import re

from models.agent_result import AgentResult
from models.assumption import AssumptionDraft, EvidenceStatus, RankedAssumption
from models.claim import ClaimStatus, VerifiedClaim

# criticality = impact (1-5) * uncertainty (1-5); at or above this the startup's
# outcome hinges on the assumption being right.
DECISION_CRITICAL_THRESHOLD = 16


def _normalize(text: str) -> str:
    """Lowercase, trim, and collapse internal whitespace for duplicate matching."""

    return re.sub(r"\s+", " ", text).strip().lower()


def _criticality(assumption: AssumptionDraft) -> int:
    return assumption.impact * assumption.uncertainty


def _deduplicate(assumptions: list[AssumptionDraft]) -> list[AssumptionDraft]:
    """Collapse exact normalized-text duplicates, keeping first ID/text/category.

    A collapsed group takes the maximum ``impact`` and ``uncertainty`` seen and
    the union of ``claim_ids``. First-occurrence order is preserved.
    """

    buckets: dict[str, dict] = {}
    order: list[str] = []
    for assumption in assumptions:
        key = _normalize(assumption.text)
        if key not in buckets:
            buckets[key] = {
                "base": assumption,
                "impact": assumption.impact,
                "uncertainty": assumption.uncertainty,
                "claim_ids": list(assumption.claim_ids),
            }
            order.append(key)
            continue
        bucket = buckets[key]
        bucket["impact"] = max(bucket["impact"], assumption.impact)
        bucket["uncertainty"] = max(bucket["uncertainty"], assumption.uncertainty)
        for claim_id in assumption.claim_ids:
            if claim_id not in bucket["claim_ids"]:
                bucket["claim_ids"].append(claim_id)

    merged: list[AssumptionDraft] = []
    for key in order:
        bucket = buckets[key]
        base = bucket["base"]
        merged.append(
            AssumptionDraft(
                id=base.id,
                text=base.text,
                category=base.category,
                impact=bucket["impact"],
                uncertainty=bucket["uncertainty"],
                supports_metric=base.supports_metric,
                claim_ids=bucket["claim_ids"],
            )
        )
    return merged


def _evidence_status(
    claim_ids: list[str],
    claims_by_id: dict[str, VerifiedClaim],
) -> EvidenceStatus:
    """Derive an evidence status from linked verified claims.

    Contradiction takes precedence over support. An assumption with no claim IDs,
    or whose claim IDs do not resolve to any verified claim, is ``UNVERIFIED``.
    """

    linked = [claims_by_id[claim_id] for claim_id in claim_ids if claim_id in claims_by_id]
    if not linked:
        return EvidenceStatus.UNVERIFIED
    statuses = {claim.status for claim in linked}
    if ClaimStatus.CONTRADICTED in statuses:
        return EvidenceStatus.CONTRADICTED
    if ClaimStatus.SUPPORTED in statuses:
        return EvidenceStatus.SUPPORTED
    if ClaimStatus.PARTIALLY_SUPPORTED in statuses:
        return EvidenceStatus.PARTIALLY_SUPPORTED
    return EvidenceStatus.UNCERTAIN


def rank_assumptions(
    agent_results: list[AgentResult],
    verified_claims: list[VerifiedClaim],
) -> list[RankedAssumption]:
    """Deduplicate, score, and rank every specialist assumption.

    Ordering: criticality desc, then impact desc, then uncertainty desc, then the
    original (post-dedup) position as a stable final tie-breaker. Ranks are
    assigned after sorting.
    """

    drafts: list[AssumptionDraft] = []
    for result in agent_results:
        drafts.extend(result.assumptions)
    deduped = _deduplicate(drafts)

    claims_by_id = {claim.claim_id: claim for claim in verified_claims}

    ordered = sorted(
        enumerate(deduped),
        key=lambda pair: (
            -_criticality(pair[1]),
            -pair[1].impact,
            -pair[1].uncertainty,
            pair[0],
        ),
    )

    ranked: list[RankedAssumption] = []
    for rank, (_, assumption) in enumerate(ordered, start=1):
        criticality = _criticality(assumption)
        ranked.append(
            RankedAssumption(
                **assumption.model_dump(),
                criticality=criticality,
                rank=rank,
                evidence_status=_evidence_status(assumption.claim_ids, claims_by_id),
                decision_critical=criticality >= DECISION_CRITICAL_THRESHOLD,
            )
        )
    return ranked
