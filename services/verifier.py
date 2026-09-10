"""Conservative deterministic claim verification for Phase 1."""

import re

from models.claim import ClaimDraft, ClaimStatus, VerifiedClaim
from models.evidence import SourceQuality
from services.evidence_store import EvidenceStore

QUALITY_WEIGHT = {SourceQuality.HIGH: 0.9, SourceQuality.MEDIUM: 0.65, SourceQuality.LOW: 0.35, SourceQuality.UNKNOWN: 0.3}
_QUALITY_RANK = {SourceQuality.HIGH: 3, SourceQuality.MEDIUM: 2, SourceQuality.LOW: 1, SourceQuality.UNKNOWN: 0}
_MIN_SUPPORTED_RANK = _QUALITY_RANK[SourceQuality.MEDIUM]
STOP_WORDS = {"the", "a", "an", "is", "are", "of", "and", "to", "in", "for", "with", "that", "this", "on"}


def _tokens(value: str) -> set[str]:
    return {token for token in re.findall(r"[a-z0-9]+", value.lower()) if token not in STOP_WORDS}


def verify_claim(claim: ClaimDraft, store: EvidenceStore) -> VerifiedClaim:
    resolved = [store.get(item) for item in claim.source_evidence_ids]
    evidence = [item for item in resolved if item is not None]
    has_unresolved_id = len(evidence) != len(claim.source_evidence_ids)
    if not evidence:
        note = "No resolvable evidence IDs were provided for this factual claim."
        if has_unresolved_id:
            note = "Every cited evidence ID is unknown; the claim is unsubstantiated."
        return VerifiedClaim(**claim.model_dump(), status=ClaimStatus.UNSUPPORTED, confidence=0.0,
            verification_notes=note)
    claim_tokens = _tokens(claim.text)
    supports, contradictions, weights = 0, 0, []
    for item in evidence:
        excerpt = item.excerpt.lower()
        overlap = len(claim_tokens & _tokens(excerpt)) / max(len(claim_tokens), 1)
        if any(phrase in excerpt for phrase in ("not ", "no evidence", "decline", "decreased", "prohibit")) and overlap >= 0.35:
            contradictions += 1
        elif claim.text.lower() in excerpt or overlap >= 0.7:
            supports += 1
            weights.append(QUALITY_WEIGHT[item.source_quality] * item.relevance_score)
        elif overlap >= 0.35:
            supports += 1
            weights.append(QUALITY_WEIGHT[item.source_quality] * item.relevance_score * 0.7)
    fully_supported = bool(supports) and all(
        claim.text.lower() in item.excerpt.lower()
        or len(claim_tokens & _tokens(item.excerpt)) / max(len(claim_tokens), 1) >= 0.7
        for item in evidence
    )
    best_rank = max(_QUALITY_RANK[item.source_quality] for item in evidence)
    if contradictions:
        status, note = ClaimStatus.CONTRADICTED, "Referenced evidence materially conflicts with the claim."
    elif fully_supported and best_rank >= _MIN_SUPPORTED_RANK and not has_unresolved_id:
        status, note = ClaimStatus.SUPPORTED, "Referenced evidence directly supports the full claim."
    elif supports:
        status, note = ClaimStatus.PARTIALLY_SUPPORTED, "Referenced evidence is relevant but does not fully establish the claim."
    else:
        status, note = ClaimStatus.UNCERTAIN, "Referenced evidence is insufficiently related to verify the claim."
    if has_unresolved_id and status != ClaimStatus.CONTRADICTED:
        note += " Some cited evidence IDs could not be resolved."
    confidence = round((sum(weights) / len(weights) if weights else 0.0) * (0.65 if contradictions else 1.0), 2)
    return VerifiedClaim(**claim.model_dump(), status=status, confidence=confidence, verification_notes=note)


def evidence_coverage(claims: list[VerifiedClaim]) -> int:
    if not claims:
        return 0
    covered = sum(claim.status in {ClaimStatus.SUPPORTED, ClaimStatus.PARTIALLY_SUPPORTED} for claim in claims)
    return round(covered / len(claims) * 100)
