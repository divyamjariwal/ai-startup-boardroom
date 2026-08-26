import unittest

from pydantic import ValidationError

from models.agent_result import (
    CTOAgentResult,
    InvestorAgentResult,
    MarketingAgentResult,
    ProductAgentResult,
)
from services.scoring import calculate_boardroom_score, calculate_cto_score


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


if __name__ == "__main__":
    unittest.main()
