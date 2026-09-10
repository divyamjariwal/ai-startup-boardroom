import unittest

from models.assumption import EvidenceStatus, RankedAssumption
from models.validation import Priority
from services.validation_engine import build_validation_plan, priority_for


def _ranked(
    assumption_id="A-INV-001",
    text="demand for the product is large",
    category="market",
    impact=4,
    uncertainty=4,
    rank=1,
    evidence_status=EvidenceStatus.UNVERIFIED,
):
    criticality = impact * uncertainty
    return RankedAssumption(
        id=assumption_id,
        text=text,
        category=category,
        impact=impact,
        uncertainty=uncertainty,
        supports_metric=None,
        claim_ids=[],
        criticality=criticality,
        rank=rank,
        evidence_status=evidence_status,
        decision_critical=criticality >= 16,
    )


def _method(category):
    plan = build_validation_plan([_ranked(category=category)])
    return plan.items[0]


class PriorityTests(unittest.TestCase):
    def test_priority_thresholds(self):
        self.assertEqual(priority_for(25), Priority.VERY_HIGH)
        self.assertEqual(priority_for(20), Priority.VERY_HIGH)
        self.assertEqual(priority_for(19), Priority.HIGH)
        self.assertEqual(priority_for(16), Priority.HIGH)
        self.assertEqual(priority_for(15), Priority.MEDIUM)
        self.assertEqual(priority_for(12), Priority.MEDIUM)
        self.assertEqual(priority_for(11), Priority.LOW)
        self.assertEqual(priority_for(1), Priority.LOW)

    def test_decision_critical_assumptions_are_at_least_high(self):
        item = build_validation_plan([_ranked(impact=4, uncertainty=4)]).items[0]
        self.assertIn(item.priority, {Priority.HIGH, Priority.VERY_HIGH})


class TemplateTests(unittest.TestCase):
    def test_customer_template(self):
        item = _method("customer")
        self.assertEqual(item.validation_method, "Customer discovery interviews")
        self.assertIn("target customers", item.success_signal)
        self.assertIn("10", item.recommended_sample)

    def test_market_uses_customer_template(self):
        self.assertEqual(
            _method("market").validation_method, "Customer discovery interviews"
        )

    def test_pricing_template(self):
        item = _method("pricing")
        self.assertEqual(
            item.validation_method, "Willingness-to-pay interviews / pricing test"
        )
        self.assertIn("price", item.success_signal)
        self.assertIn("10", item.recommended_sample)

    def test_acquisition_template(self):
        item = _method("acquisition")
        self.assertEqual(
            item.validation_method, "Landing-page or acquisition experiment"
        )
        self.assertEqual(item.recommended_sample, "50 targeted visitors/leads")

    def test_retention_template(self):
        item = _method("retention")
        self.assertEqual(item.validation_method, "Pilot / cohort retention test")
        self.assertEqual(item.recommended_sample, "10 pilot users")

    def test_technology_template(self):
        item = _method("technology")
        self.assertEqual(item.validation_method, "Technical prototype / load test")
        self.assertEqual(item.recommended_sample, "1 representative prototype test")

    def test_scalability_uses_technology_template(self):
        self.assertEqual(
            _method("scalability").validation_method,
            "Technical prototype / load test",
        )

    def test_unknown_category_falls_back_to_customer_discovery(self):
        item = _method("astrology_alignment")
        self.assertEqual(item.validation_method, "Customer discovery interviews")
        self.assertEqual(
            item.recommended_sample, "10 customer discovery interviews"
        )
        self.assertIn("holds in practice", item.success_signal)


class PlanShapeTests(unittest.TestCase):
    def _sample(self):
        return [
            _ranked(assumption_id="A-INV-001", text="demand is large", category="market",
                    impact=5, uncertainty=5, rank=1),
            _ranked(assumption_id="A-MKT-001", text="acquisition is cheap", category="acquisition",
                    impact=4, uncertainty=4, rank=2),
            _ranked(assumption_id="A-CTO-001", text="it scales", category="scalability",
                    impact=3, uncertainty=3, rank=3),
        ]

    def test_ranked_order_is_preserved(self):
        plan = build_validation_plan(self._sample())
        self.assertEqual([item.rank for item in plan.items], [1, 2, 3])
        self.assertEqual(
            [item.assumption_id for item in plan.items],
            ["A-INV-001", "A-MKT-001", "A-CTO-001"],
        )

    def test_only_the_supplied_assumptions_are_included(self):
        supplied = self._sample()
        plan = build_validation_plan(supplied)
        self.assertEqual(len(plan.items), len(supplied))
        self.assertEqual(
            {item.assumption_id for item in plan.items},
            {a.id for a in supplied},
        )

    def test_empty_input_yields_empty_plan(self):
        self.assertEqual(build_validation_plan([]).items, [])

    def test_test_question_is_derived_from_assumption_text(self):
        plan = build_validation_plan([_ranked(text="buyers will pay monthly.")])
        self.assertEqual(
            plan.items[0].test_question, "Can we verify that: buyers will pay monthly?"
        )

    def test_output_is_deterministic(self):
        supplied = self._sample()
        first = build_validation_plan(supplied)
        second = build_validation_plan(supplied)
        self.assertEqual(first.model_dump(), second.model_dump())

    def test_rationale_flags_decision_critical(self):
        plan = build_validation_plan([_ranked(impact=5, uncertainty=5)])
        self.assertIn("Decision-critical", plan.items[0].rationale)


if __name__ == "__main__":
    unittest.main()
