import unittest

from models.agent_result import (
    CTOAgentResult,
    InvestorAgentResult,
    MarketingAgentResult,
    ProductAgentResult,
)
from models.assumption import AssumptionDraft, EvidenceStatus, RankedAssumption
from models.sensitivity import MappingStatus
from services.scoring import (
    calculate_boardroom_score,
    calculate_investor_score,
    get_investment_decision,
)
from services.sensitivity_engine import clamp_score, run_sensitivity


def _draft(
    assumption_id="A-INV-001",
    text="demand for the product is large and durable",
    category="market",
    impact=5,
    uncertainty=5,
    supports_metric=None,
):
    return AssumptionDraft(
        id=assumption_id,
        text=text,
        category=category,
        impact=impact,
        uncertainty=uncertainty,
        supports_metric=supports_metric,
        claim_ids=[],
    )


def _ranked(draft, *, rank=1, criticality=None, decision_critical=None):
    criticality = criticality if criticality is not None else draft.impact * draft.uncertainty
    decision_critical = (
        decision_critical if decision_critical is not None else criticality >= 16
    )
    return RankedAssumption(
        **draft.model_dump(),
        criticality=criticality,
        rank=rank,
        evidence_status=EvidenceStatus.UNVERIFIED,
        decision_critical=decision_critical,
    )


def _investor(assumptions=(), **overrides):
    scores = dict(
        market_score=8, revenue_score=7, scalability_score=9, risk_management_score=6
    )
    scores.update(overrides)
    return InvestorAgentResult(
        **scores,
        strengths=["a", "b", "c"],
        weaknesses=["d", "e", "f"],
        recommendation="Proceed after validating demand.",
        assumptions=list(assumptions),
    )


def _cto(assumptions=(), **overrides):
    scores = dict(
        technical_feasibility_score=7,
        scalability_score=7,
        infrastructure_simplicity_score=7,
        security_posture_score=8,
        cost_efficiency_score=7,
    )
    scores.update(overrides)
    return CTOAgentResult(
        **scores,
        strengths=["a", "b", "c"],
        weaknesses=["d", "e", "f"],
        recommendation="Build a focused first release.",
        assumptions=list(assumptions),
    )


def _marketing(assumptions=(), **overrides):
    scores = dict(
        customer_acquisition_score=7,
        brand_differentiation_score=7,
        growth_potential_score=7,
        go_to_market_score=8,
        retention_score=7,
    )
    scores.update(overrides)
    return MarketingAgentResult(
        **scores,
        strengths=["a", "b", "c"],
        weaknesses=["d", "e", "f"],
        recommendation="Start with a narrow segment.",
        assumptions=list(assumptions),
    )


def _product(assumptions=(), **overrides):
    scores = dict(
        product_market_fit_score=7,
        user_experience_score=7,
        feature_differentiation_score=8,
        retention_score=7,
        product_vision_score=7,
    )
    scores.update(overrides)
    return ProductAgentResult(
        **scores,
        strengths=["a", "b", "c"],
        weaknesses=["d", "e", "f"],
        recommendation="Validate the core workflow first.",
        assumptions=list(assumptions),
    )


def _run(investor, cto, marketing, product, ranked):
    board = calculate_boardroom_score(investor, cto, marketing, product)
    band = get_investment_decision(board)
    return board, band, run_sensitivity(
        investor, cto, marketing, product, board, band, ranked
    )


class ScenarioSelectionTests(unittest.TestCase):
    def test_only_decision_critical_assumptions_generate_scenarios(self):
        critical_draft = _draft(text="buyers exist in volume", impact=5, uncertainty=5)
        minor_draft = _draft(
            assumption_id="A-INV-002", text="branding will be easy", impact=3, uncertainty=3
        )
        investor = _investor([critical_draft, minor_draft])
        ranked = [
            _ranked(critical_draft, rank=1),
            _ranked(minor_draft, rank=2),  # criticality 9 -> not decision-critical
        ]
        _, _, result = _run(investor, _cto(), _marketing(), _product(), ranked)
        self.assertEqual(len(result.scenarios), 1)
        self.assertEqual(result.scenarios[0].assumption_text, "buyers exist in volume")
        self.assertEqual(result.decision_critical_count, 1)

    def test_multiple_assumptions_produce_independent_scenarios(self):
        inv_draft = _draft(
            assumption_id="A-INV-001", text="demand is large", impact=5, uncertainty=5
        )
        cto_draft = _draft(
            assumption_id="A-CTO-001",
            text="the system scales affordably",
            category="scalability",
            impact=5,
            uncertainty=4,
        )
        investor = _investor([inv_draft])
        cto = _cto([cto_draft])
        marketing, product = _marketing(), _product()
        board, band, result = _run(
            investor, cto, marketing, product, [_ranked(inv_draft, rank=1), _ranked(cto_draft, rank=2)]
        )
        self.assertEqual(len(result.scenarios), 2)

        # Each scenario is measured from the untouched baseline, not compounded.
        inv_penalty = 0.20 * 1.0 * 1.0
        expected_inv_board = round(
            (
                calculate_investor_score(investor) * (1 - inv_penalty)
                + result_specialist(cto)
                + result_specialist(marketing)
                + result_specialist(product)
            )
            / 4
        )
        by_id = {s.assumption_id: s for s in result.scenarios}
        self.assertEqual(by_id["A-INV-001"].scenario_boardroom_score, expected_inv_board)
        self.assertEqual(by_id["A-INV-001"].score_delta, expected_inv_board - board)

        cto_penalty = 0.20 * 1.0 * (4 / 5)
        expected_cto_board = round(
            (
                result_specialist(investor)
                + result_specialist(cto) * (1 - cto_penalty)
                + result_specialist(marketing)
                + result_specialist(product)
            )
            / 4
        )
        self.assertEqual(by_id["A-CTO-001"].scenario_boardroom_score, expected_cto_board)


class MappedMetricTests(unittest.TestCase):
    def test_mapped_metric_scenario_changes_the_hypothetical_score(self):
        draft = _draft(text="the market is large", supports_metric="market_score")
        investor = _investor([draft])
        board, _, result = _run(investor, _cto(), _marketing(), _product(), [_ranked(draft)])
        scenario = result.scenarios[0]
        self.assertEqual(scenario.mapping_status, MappingStatus.MAPPED_METRIC)
        self.assertEqual(scenario.affected_specialists, ["Investor"])
        self.assertEqual(scenario.affected_metric, "market_score")

        # market_score 8 -> 8 * 0.8 = 6.4; investor 75.0 -> 71.0
        scenario_investor = round((6.4 * 10 + 7 * 10 + 9 * 10 + 6 * 10) / 4, 2)
        self.assertEqual(scenario_investor, 71.0)
        expected_board = round(
            (
                scenario_investor
                + result_specialist(_cto())
                + result_specialist(_marketing())
                + result_specialist(_product())
            )
            / 4
        )
        self.assertEqual(scenario.scenario_boardroom_score, expected_board)
        self.assertLess(scenario.scenario_boardroom_score, board)

    def test_score_delta_matches_recomputed_boardroom(self):
        draft = _draft(text="the market is large", supports_metric="market_score")
        investor = _investor([draft])
        board, _, result = _run(investor, _cto(), _marketing(), _product(), [_ranked(draft)])
        scenario = result.scenarios[0]
        self.assertEqual(
            scenario.score_delta, scenario.scenario_boardroom_score - board
        )
        self.assertEqual(scenario.current_boardroom_score, board)


class UnmappedTests(unittest.TestCase):
    def test_supports_metric_not_owned_yields_unmapped_without_delta(self):
        # Investor has no retention_score metric.
        draft = _draft(text="users will stick around", supports_metric="retention_score")
        investor = _investor([draft])
        _, _, result = _run(investor, _cto(), _marketing(), _product(), [_ranked(draft)])
        scenario = result.scenarios[0]
        self.assertEqual(scenario.mapping_status, MappingStatus.UNMAPPED)
        self.assertIsNone(scenario.scenario_boardroom_score)
        self.assertIsNone(scenario.score_delta)
        self.assertIsNone(scenario.scenario_band)
        self.assertFalse(scenario.band_changed)

    def test_assumption_with_no_owning_specialist_is_unmapped(self):
        draft = _draft(text="this text is only in the ranked list")
        # investor's own drafts do not include this text
        investor = _investor([_draft(text="a totally different assumption")])
        _, _, result = _run(investor, _cto(), _marketing(), _product(), [_ranked(draft)])
        scenario = result.scenarios[0]
        self.assertEqual(scenario.mapping_status, MappingStatus.UNMAPPED)
        self.assertIsNone(scenario.score_delta)


class ClampAndPurityTests(unittest.TestCase):
    def test_clamp_score_confines_to_zero_hundred(self):
        self.assertEqual(clamp_score(-5.0), 0.0)
        self.assertEqual(clamp_score(150.0), 100.0)
        self.assertEqual(clamp_score(42.5), 42.5)

    def test_scenario_scores_stay_within_bounds(self):
        draft = _draft(text="the market is large", supports_metric="market_score")
        investor = _investor([draft])
        _, _, result = _run(investor, _cto(), _marketing(), _product(), [_ranked(draft)])
        for scenario in result.scenarios:
            if scenario.scenario_boardroom_score is not None:
                self.assertGreaterEqual(scenario.scenario_boardroom_score, 0)
                self.assertLessEqual(scenario.scenario_boardroom_score, 100)

    def test_current_scores_are_not_mutated(self):
        draft = _draft(text="the market is large", supports_metric="market_score")
        investor = _investor([draft])
        before = calculate_investor_score(investor)
        raw_before = investor.market_score
        _run(investor, _cto(), _marketing(), _product(), [_ranked(draft)])
        self.assertEqual(calculate_investor_score(investor), before)
        self.assertEqual(investor.market_score, raw_before)


class BandRecalculationTests(unittest.TestCase):
    def _borderline_board(self):
        # Specialist scores: 72.5 / 72.0 / 72.0 / 70.0 -> boardroom 72 (CAUTION).
        investor = _investor(
            market_score=8, revenue_score=7, scalability_score=7, risk_management_score=7
        )
        cto = _cto(
            technical_feasibility_score=7,
            scalability_score=7,
            infrastructure_simplicity_score=7,
            security_posture_score=8,
            cost_efficiency_score=7,
        )
        marketing = _marketing(
            customer_acquisition_score=7,
            brand_differentiation_score=7,
            growth_potential_score=7,
            go_to_market_score=8,
            retention_score=7,
        )
        product = _product(
            product_market_fit_score=7,
            user_experience_score=7,
            feature_differentiation_score=7,
            retention_score=7,
            product_vision_score=7,
        )
        return investor, cto, marketing, product

    def test_investment_band_is_recalculated_on_failure(self):
        investor, cto, marketing, product = self._borderline_board()
        draft = _draft(text="the whole investment case holds", supports_metric=None)
        investor.assumptions = [draft]
        board, band, result = _run(investor, cto, marketing, product, [_ranked(draft)])
        self.assertEqual(board, 72)
        self.assertIn("CAUTION", band)

        scenario = result.scenarios[0]
        self.assertEqual(scenario.mapping_status, MappingStatus.MAPPED_SPECIALIST)
        # investor 72.5 -> 58.0 ; boardroom round((58+72+72+70)/4) = 68 -> HIGH RISK
        self.assertEqual(scenario.scenario_boardroom_score, 68)
        self.assertEqual(scenario.score_delta, -4)
        self.assertTrue(scenario.band_changed)
        self.assertIn("HIGH RISK", scenario.scenario_band)
        self.assertEqual(result.band_changing_count, 1)


def result_specialist(result):
    """Score a freshly-built specialist result (helper for expected values)."""

    from services.scoring import (
        calculate_cto_score,
        calculate_investor_score,
        calculate_marketing_score,
        calculate_product_score,
    )

    return {
        InvestorAgentResult: calculate_investor_score,
        CTOAgentResult: calculate_cto_score,
        MarketingAgentResult: calculate_marketing_score,
        ProductAgentResult: calculate_product_score,
    }[type(result)](result)


if __name__ == "__main__":
    unittest.main()
