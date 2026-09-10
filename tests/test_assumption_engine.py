import unittest

from models.agent_result import CTOAgentResult, InvestorAgentResult
from models.assumption import AssumptionDraft, EvidenceStatus, RankedAssumption
from models.claim import ClaimStatus, VerifiedClaim
from models.evidence import ResearchCategory
from services.assumption_engine import DECISION_CRITICAL_THRESHOLD, rank_assumptions


def _assumption(
    assumption_id="A-INV-001",
    text="demand for the product exists",
    category="market",
    impact=4,
    uncertainty=4,
    supports_metric=None,
    claim_ids=None,
):
    return AssumptionDraft(
        id=assumption_id,
        text=text,
        category=category,
        impact=impact,
        uncertainty=uncertainty,
        supports_metric=supports_metric,
        claim_ids=claim_ids or [],
    )


def _investor(assumptions):
    return InvestorAgentResult(
        market_score=5,
        revenue_score=5,
        scalability_score=5,
        risk_management_score=5,
        strengths=["a", "b", "c"],
        weaknesses=["d", "e", "f"],
        recommendation="Proceed after validating demand.",
        assumptions=assumptions,
    )


def _cto(assumptions):
    return CTOAgentResult(
        technical_feasibility_score=5,
        scalability_score=5,
        infrastructure_simplicity_score=5,
        security_posture_score=5,
        cost_efficiency_score=5,
        strengths=["a", "b", "c"],
        weaknesses=["d", "e", "f"],
        recommendation="Build a focused first release.",
        assumptions=assumptions,
    )


def _claim(claim_id, status):
    return VerifiedClaim(
        claim_id=claim_id,
        text="the addressable market is large",
        category=ResearchCategory.MARKET,
        source_evidence_ids=[],
        importance=3,
        supports_metric=None,
        status=status,
        confidence=0.5,
        verification_notes="constructed for tests",
    )


class CriticalityAndThresholdTests(unittest.TestCase):
    def test_criticality_is_impact_times_uncertainty(self):
        ranked = rank_assumptions([_investor([_assumption(impact=3, uncertainty=4)])], [])
        self.assertEqual(ranked[0].criticality, 12)

    def test_threshold_constant_is_sixteen(self):
        self.assertEqual(DECISION_CRITICAL_THRESHOLD, 16)

    def test_criticality_at_threshold_is_decision_critical(self):
        ranked = rank_assumptions([_investor([_assumption(impact=4, uncertainty=4)])], [])
        self.assertEqual(ranked[0].criticality, 16)
        self.assertTrue(ranked[0].decision_critical)

    def test_criticality_below_threshold_is_not_decision_critical(self):
        ranked = rank_assumptions([_investor([_assumption(impact=3, uncertainty=5)])], [])
        self.assertEqual(ranked[0].criticality, 15)
        self.assertFalse(ranked[0].decision_critical)


class RankingTests(unittest.TestCase):
    def test_assumptions_are_ordered_by_criticality_descending(self):
        assumptions = [
            _assumption(assumption_id="A-INV-001", text="low", impact=3, uncertainty=3),      # 9
            _assumption(assumption_id="A-INV-002", text="high", impact=5, uncertainty=5),      # 25
            _assumption(assumption_id="A-INV-003", text="mid", impact=3, uncertainty=4),       # 12
        ]
        ranked = rank_assumptions([_investor(assumptions)], [])
        self.assertEqual([item.text for item in ranked], ["high", "mid", "low"])
        self.assertEqual([item.rank for item in ranked], [1, 2, 3])
        self.assertEqual([item.criticality for item in ranked], [25, 12, 9])

    def test_tie_break_prefers_higher_impact_then_uncertainty(self):
        assumptions = [
            _assumption(assumption_id="A-INV-001", text="lower impact", impact=3, uncertainty=4),   # 12
            _assumption(assumption_id="A-INV-002", text="higher impact", impact=4, uncertainty=3),   # 12
        ]
        ranked = rank_assumptions([_investor(assumptions)], [])
        self.assertEqual([item.text for item in ranked], ["higher impact", "lower impact"])

    def test_full_tie_falls_back_to_original_order(self):
        assumptions = [
            _assumption(assumption_id="A-INV-001", text="first", impact=4, uncertainty=3),
            _assumption(assumption_id="A-INV-002", text="second", impact=4, uncertainty=3),
        ]
        ranked = rank_assumptions([_investor(assumptions)], [])
        self.assertEqual([item.text for item in ranked], ["first", "second"])
        self.assertEqual([item.rank for item in ranked], [1, 2])

    def test_ranking_is_deterministic_across_input_permutations(self):
        assumptions = [
            _assumption(assumption_id="A-INV-001", text="alpha", impact=4, uncertainty=3),
            _assumption(assumption_id="A-INV-002", text="beta", impact=4, uncertainty=3),
            _assumption(assumption_id="A-INV-003", text="gamma", impact=5, uncertainty=5),
        ]
        first = rank_assumptions([_investor(assumptions)], [])
        again = rank_assumptions([_investor(assumptions)], [])
        self.assertEqual([item.text for item in first], [item.text for item in again])


class DeduplicationTests(unittest.TestCase):
    def test_exact_normalized_duplicates_collapse(self):
        assumptions = [
            _assumption(assumption_id="A-INV-001", text="Demand Exists"),
            _assumption(assumption_id="A-INV-002", text="  demand   exists "),
        ]
        ranked = rank_assumptions([_investor(assumptions)], [])
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0].id, "A-INV-001")
        self.assertEqual(ranked[0].text, "Demand Exists")

    def test_merge_keeps_max_impact_and_uncertainty(self):
        assumptions = [
            _assumption(assumption_id="A-INV-001", text="demand exists", impact=2, uncertainty=5),
            _assumption(assumption_id="A-INV-002", text="demand exists", impact=4, uncertainty=1),
        ]
        ranked = rank_assumptions([_investor(assumptions)], [])
        self.assertEqual(len(ranked), 1)
        self.assertEqual(ranked[0].impact, 4)
        self.assertEqual(ranked[0].uncertainty, 5)
        self.assertEqual(ranked[0].criticality, 20)

    def test_merge_unions_claim_ids(self):
        assumptions = [
            _assumption(assumption_id="A-INV-001", text="demand exists", claim_ids=["C-INV-001"]),
            _assumption(assumption_id="A-INV-002", text="demand exists", claim_ids=["C-INV-002", "C-INV-001"]),
        ]
        ranked = rank_assumptions([_investor(assumptions)], [])
        self.assertEqual(ranked[0].claim_ids, ["C-INV-001", "C-INV-002"])


class EvidenceStatusTests(unittest.TestCase):
    def test_supported_when_a_linked_claim_is_supported(self):
        assumptions = [_assumption(claim_ids=["C-INV-001"])]
        claims = [_claim("C-INV-001", ClaimStatus.SUPPORTED)]
        ranked = rank_assumptions([_investor(assumptions)], claims)
        self.assertEqual(ranked[0].evidence_status, EvidenceStatus.SUPPORTED)

    def test_partially_supported_when_only_partial_evidence_exists(self):
        assumptions = [_assumption(claim_ids=["C-INV-001", "C-INV-002"])]
        claims = [
            _claim("C-INV-001", ClaimStatus.PARTIALLY_SUPPORTED),
            _claim("C-INV-002", ClaimStatus.UNCERTAIN),
        ]
        ranked = rank_assumptions([_investor(assumptions)], claims)
        self.assertEqual(ranked[0].evidence_status, EvidenceStatus.PARTIALLY_SUPPORTED)

    def test_contradicted_when_a_linked_claim_is_contradicted(self):
        assumptions = [_assumption(claim_ids=["C-INV-001"])]
        claims = [_claim("C-INV-001", ClaimStatus.CONTRADICTED)]
        ranked = rank_assumptions([_investor(assumptions)], claims)
        self.assertEqual(ranked[0].evidence_status, EvidenceStatus.CONTRADICTED)

    def test_contradiction_takes_precedence_over_support(self):
        assumptions = [_assumption(claim_ids=["C-INV-001", "C-INV-002"])]
        claims = [
            _claim("C-INV-001", ClaimStatus.SUPPORTED),
            _claim("C-INV-002", ClaimStatus.CONTRADICTED),
        ]
        ranked = rank_assumptions([_investor(assumptions)], claims)
        self.assertEqual(ranked[0].evidence_status, EvidenceStatus.CONTRADICTED)

    def test_uncertain_when_linked_claims_offer_no_stronger_status(self):
        assumptions = [_assumption(claim_ids=["C-INV-001"])]
        claims = [_claim("C-INV-001", ClaimStatus.UNSUPPORTED)]
        ranked = rank_assumptions([_investor(assumptions)], claims)
        self.assertEqual(ranked[0].evidence_status, EvidenceStatus.UNCERTAIN)

    def test_unverified_when_no_claim_ids(self):
        ranked = rank_assumptions([_investor([_assumption(claim_ids=[])])], [])
        self.assertEqual(ranked[0].evidence_status, EvidenceStatus.UNVERIFIED)

    def test_unverified_when_claim_ids_do_not_resolve(self):
        assumptions = [_assumption(claim_ids=["C-INV-404"])]
        claims = [_claim("C-INV-001", ClaimStatus.SUPPORTED)]
        ranked = rank_assumptions([_investor(assumptions)], claims)
        self.assertEqual(ranked[0].evidence_status, EvidenceStatus.UNVERIFIED)


class CollectionTests(unittest.TestCase):
    def test_empty_assumptions_yield_empty_ranking(self):
        self.assertEqual(rank_assumptions([_investor([])], []), [])

    def test_no_agents_yield_empty_ranking(self):
        self.assertEqual(rank_assumptions([], []), [])

    def test_assumptions_are_collected_across_multiple_agents(self):
        investor = _investor([
            _assumption(assumption_id="A-INV-001", text="buyers will pay monthly", impact=5, uncertainty=5),
        ])
        cto = _cto([
            _assumption(assumption_id="A-CTO-001", text="the model can be served cheaply", impact=3, uncertainty=2),
            _assumption(assumption_id="A-CTO-002", text="latency stays acceptable at scale", impact=4, uncertainty=3),
        ])
        ranked = rank_assumptions([investor, cto], [])
        self.assertEqual(len(ranked), 3)
        self.assertIsInstance(ranked[0], RankedAssumption)
        self.assertEqual(ranked[0].text, "buyers will pay monthly")
        self.assertEqual([item.rank for item in ranked], [1, 2, 3])
        self.assertTrue(ranked[0].decision_critical)
        self.assertFalse(ranked[2].decision_critical)


if __name__ == "__main__":
    unittest.main()
