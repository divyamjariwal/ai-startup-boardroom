import unittest
from datetime import datetime, timezone

from pydantic import ValidationError

from models.agent_result import (
    CTOAgentResult,
    InvestorAgentResult,
    MarketingAgentResult,
    ProductAgentResult,
)
from models.claim import ClaimDraft, ClaimStatus, VerifiedClaim
from models.evidence import Evidence, ResearchCategory, SourceQuality, SourceType
from services.evidence_store import EvidenceStore
from services.scoring import (
    calculate_boardroom_score,
    calculate_cto_score,
    calculate_investor_score,
)
from services.verifier import verify_claim


class AgentModelAndScoringTests(unittest.TestCase):
    def setUp(self):
        self.investor = InvestorAgentResult(
            market_score=8,
            revenue_score=7,
            scalability_score=9,
            risk_management_score=6,
            strengths=["a", "b", "c"],
            weaknesses=["d", "e", "f"],
            recommendation="Proceed after validating demand.",
        )
        self.cto = CTOAgentResult(
            technical_feasibility_score=8,
            scalability_score=9,
            infrastructure_simplicity_score=7,
            security_posture_score=8,
            cost_efficiency_score=6,
            strengths=["a", "b", "c"],
            weaknesses=["d", "e", "f"],
            recommendation="Build a focused first release.",
        )
        self.marketing = MarketingAgentResult(
            customer_acquisition_score=7,
            brand_differentiation_score=6,
            growth_potential_score=8,
            go_to_market_score=7,
            retention_score=7,
            strengths=["a", "b", "c"],
            weaknesses=["d", "e", "f"],
            recommendation="Start with a narrow segment.",
        )
        self.product = ProductAgentResult(
            product_market_fit_score=8,
            user_experience_score=7,
            feature_differentiation_score=6,
            retention_score=7,
            product_vision_score=8,
            strengths=["a", "b", "c"],
            weaknesses=["d", "e", "f"],
            recommendation="Validate the core workflow first.",
        )

    def test_negative_cto_concepts_are_expressed_as_positive_metrics(self):
        self.assertEqual(calculate_cto_score(self.cto), 76.0)

    def test_boardroom_score_uses_every_positive_metric(self):
        self.assertEqual(
            calculate_boardroom_score(
                self.investor,
                self.cto,
                self.marketing,
                self.product,
            ),
            73,
        )

    def test_schema_rejects_out_of_range_scores_and_extra_fields(self):
        payload = self.investor.model_dump()
        payload["market_score"] = 11
        payload["unexpected"] = "not allowed"

        with self.assertRaises(ValidationError):
            InvestorAgentResult.model_validate(payload)


def _verified_claim(status, importance=3, supports_metric=None, claim_id="C-INV-001"):
    return VerifiedClaim(
        claim_id=claim_id,
        text="the addressable market is large",
        category=ResearchCategory.MARKET,
        source_evidence_ids=[],
        importance=importance,
        supports_metric=supports_metric,
        status=status,
        confidence=0.5,
        verification_notes="constructed for tests",
    )


def _evidence(evidence_id, excerpt, quality=SourceQuality.HIGH):
    return Evidence(
        evidence_id=evidence_id,
        category=ResearchCategory.MARKET,
        topic="market size",
        title="Reference report",
        source_url=f"https://example.gov/{evidence_id}",
        source_name="example.gov",
        source_type=SourceType.GOVERNMENT,
        source_quality=quality,
        excerpt=excerpt,
        relevance_score=0.9,
        retrieved_at=datetime.now(timezone.utc),
    )


class EvidenceAwareScoringTests(unittest.TestCase):
    def setUp(self):
        self.investor = InvestorAgentResult(
            market_score=8,
            revenue_score=7,
            scalability_score=9,
            risk_management_score=6,
            strengths=["a", "b", "c"],
            weaknesses=["d", "e", "f"],
            recommendation="Proceed after validating demand.",
        )
        self.baseline = round((8 + 7 + 9 + 6) / 4 * 10, 2)  # 75.0

    def test_supported_claim_leaves_score_unchanged(self):
        self.investor.verified_claims = [
            _verified_claim(ClaimStatus.SUPPORTED, importance=5)
        ]
        self.assertEqual(calculate_investor_score(self.investor), self.baseline)

    def test_contradicted_critical_claim_reduces_score(self):
        self.investor.verified_claims = [
            _verified_claim(ClaimStatus.CONTRADICTED, importance=5)
        ]
        adjusted = calculate_investor_score(self.investor)
        self.assertLess(adjusted, self.baseline)
        self.assertAlmostEqual(adjusted, self.baseline * 0.6, places=2)

    def test_penalties_cannot_push_multiplier_below_floor(self):
        self.investor.verified_claims = [
            _verified_claim(ClaimStatus.CONTRADICTED, importance=5, claim_id="C-INV-001"),
            _verified_claim(ClaimStatus.CONTRADICTED, importance=5, claim_id="C-INV-002"),
            _verified_claim(ClaimStatus.UNSUPPORTED, importance=5, claim_id="C-INV-003"),
        ]
        adjusted = calculate_investor_score(self.investor)
        self.assertAlmostEqual(adjusted, self.baseline * 0.5, places=2)

    def test_no_claims_leaves_score_unchanged(self):
        self.investor.verified_claims = []
        self.assertEqual(calculate_investor_score(self.investor), self.baseline)

    def test_supports_metric_scopes_penalty_to_target_metric(self):
        self.investor.verified_claims = [
            _verified_claim(
                ClaimStatus.CONTRADICTED, importance=5, supports_metric="market_score"
            )
        ]
        adjusted = calculate_investor_score(self.investor)
        expected = round((8 * 10 * 0.6 + 7 * 10 + 9 * 10 + 6 * 10) / 4, 2)
        self.assertEqual(adjusted, expected)
        self.assertGreater(adjusted, self.baseline * 0.6)

    def test_unknown_supports_metric_falls_back_to_agent_level(self):
        self.investor.verified_claims = [
            _verified_claim(
                ClaimStatus.CONTRADICTED, importance=5, supports_metric="retention_score"
            )
        ]
        adjusted = calculate_investor_score(self.investor)
        self.assertAlmostEqual(adjusted, self.baseline * 0.6, places=2)


class VerifierSafetyTests(unittest.TestCase):
    def test_fake_evidence_id_cannot_be_supported(self):
        store = EvidenceStore()
        store.add(
            _evidence("E-001", "the addressable market is large and growing worldwide")
        )
        claim = ClaimDraft(
            claim_id="C-INV-001",
            text="the addressable market is large",
            category=ResearchCategory.MARKET,
            source_evidence_ids=["E-001", "E-404"],
            importance=4,
        )
        verified = verify_claim(claim, store)
        self.assertNotEqual(verified.status, ClaimStatus.SUPPORTED)

    def test_contradiction_is_not_downgraded_to_partial_support(self):
        store = EvidenceStore()
        store.add(_evidence("E-001", "the addressable market is large and expanding"))
        store.add(
            _evidence(
                "E-002",
                "the addressable market is large but demand has declined and is not growing",
            )
        )
        claim = ClaimDraft(
            claim_id="C-INV-001",
            text="the addressable market is large and growing",
            category=ResearchCategory.MARKET,
            source_evidence_ids=["E-001", "E-002"],
            importance=4,
        )
        verified = verify_claim(claim, store)
        self.assertEqual(verified.status, ClaimStatus.CONTRADICTED)

    def test_supported_requires_at_least_medium_quality_source(self):
        store = EvidenceStore()
        store.add(
            _evidence(
                "E-001",
                "the addressable market is large",
                quality=SourceQuality.UNKNOWN,
            )
        )
        claim = ClaimDraft(
            claim_id="C-INV-001",
            text="the addressable market is large",
            category=ResearchCategory.MARKET,
            source_evidence_ids=["E-001"],
            importance=3,
        )
        verified = verify_claim(claim, store)
        self.assertEqual(verified.status, ClaimStatus.PARTIALLY_SUPPORTED)


if __name__ == "__main__":
    unittest.main()
