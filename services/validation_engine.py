"""Deterministic founder validation plan from ranked assumptions.

One ``ValidationItem`` per ranked assumption, in the order given. Priority
comes from a fixed criticality ladder; method, success signal, and sample
size come from category-keyword templates. No LLM call, no NLP.
"""

from models.assumption import RankedAssumption
from models.validation import (
    PRIORITY_HIGH_MIN,
    PRIORITY_MEDIUM_MIN,
    PRIORITY_VERY_HIGH_MIN,
    SAMPLE_ACQUISITION,
    SAMPLE_INTERVIEWS,
    SAMPLE_PRICING,
    SAMPLE_RETENTION_PILOT,
    SAMPLE_TECH_PROTOTYPE,
    Priority,
    ValidationItem,
    ValidationPlan,
)


class _Template:
    __slots__ = ("method", "success_signal", "recommended_sample")

    def __init__(self, method: str, success_signal: str, recommended_sample: str):
        self.method = method
        self.success_signal = success_signal
        self.recommended_sample = recommended_sample


_CUSTOMER_MARKET = _Template(
    "Customer discovery interviews",
    "At least 5 of 10 target customers independently confirm the problem is "
    "frequent and important.",
    f"{SAMPLE_INTERVIEWS} target-customer interviews",
)
_PRICING = _Template(
    "Willingness-to-pay interviews / pricing test",
    "At least 3 of 10 target customers accept or seriously engage with the "
    "proposed price.",
    f"{SAMPLE_PRICING} willingness-to-pay interviews",
)
_ACQUISITION = _Template(
    "Landing-page or acquisition experiment",
    "A measurable acquisition channel produces qualified leads at a repeatable "
    "cost.",
    f"{SAMPLE_ACQUISITION} targeted visitors/leads",
)
_RETENTION = _Template(
    "Pilot / cohort retention test",
    "Pilot users continue using the product after the initial trial period.",
    f"{SAMPLE_RETENTION_PILOT} pilot users",
)
_TECHNOLOGY = _Template(
    "Technical prototype / load test",
    "Prototype meets the required functional/performance constraint under a "
    "defined test.",
    f"{SAMPLE_TECH_PROTOTYPE} representative prototype test",
)
_PRODUCT = _Template(
    "Prototype usability test",
    "Most test users complete the core workflow in a prototype without "
    "assistance.",
    f"{SAMPLE_INTERVIEWS} usability sessions",
)
_BUSINESS_MODEL = _Template(
    "Pricing / business-model experiment",
    "A live test of the pricing or revenue mechanism shows customers will "
    "transact on the proposed terms.",
    f"{SAMPLE_PRICING} willingness-to-pay interviews",
)
_FALLBACK = _Template(
    "Customer discovery interviews",
    "At least 5 of 10 target customers independently confirm the assumption "
    "holds in practice.",
    f"{SAMPLE_INTERVIEWS} customer discovery interviews",
)

# Checked in order; the first template with a keyword contained in the
# (lowercased) category label wins. Order matters where labels overlap
# (e.g. "go_to_market" contains "market" but pricing/acquisition are checked
# first).
_TEMPLATE_RULES: tuple[tuple[tuple[str, ...], _Template], ...] = (
    (("pricing", "price", "willingness", "monetization", "monetisation"), _PRICING),
    (("acquisition", "channel", "lead", "cac", "funnel", "traffic"), _ACQUISITION),
    (("retention", "churn", "engagement", "stickiness", "renewal"), _RETENTION),
    (("business_model", "business-model", "unit_economics", "revenue_model"), _BUSINESS_MODEL),
    (
        ("technology", "technical", "scalability", "infrastructure", "performance",
         "latency", "security", "feasibility"),
        _TECHNOLOGY,
    ),
    (("product", "usability", "ux", "feature", "workflow", "onboarding"), _PRODUCT),
    (("customer", "market", "demand", "segment", "need", "problem", "adoption"), _CUSTOMER_MARKET),
)


def _template_for(category: str) -> _Template:
    key = category.strip().lower()
    for keywords, template in _TEMPLATE_RULES:
        if any(word in key for word in keywords):
            return template
    return _FALLBACK


def priority_for(criticality: int) -> Priority:
    if criticality >= PRIORITY_VERY_HIGH_MIN:
        return Priority.VERY_HIGH
    if criticality >= PRIORITY_HIGH_MIN:
        return Priority.HIGH
    if criticality >= PRIORITY_MEDIUM_MIN:
        return Priority.MEDIUM
    return Priority.LOW


def _test_question(text: str) -> str:
    return f"Can we verify that: {text.strip().rstrip('.?!').strip()}?"


def _rationale(assumption: RankedAssumption) -> str:
    urgency = (
        "Decision-critical - validate before committing significant resources."
        if assumption.decision_critical
        else "Validate to reduce residual uncertainty before scaling."
    )
    return (
        f"Criticality {assumption.criticality} "
        f"(impact {assumption.impact} x uncertainty {assumption.uncertainty}); "
        f"current evidence status is "
        f"{assumption.evidence_status.value.replace('_', ' ')}. {urgency}"
    )


def build_validation_plan(
    ranked_assumptions: list[RankedAssumption],
) -> ValidationPlan:
    """One founder-facing test per ranked assumption, in the given order."""

    items: list[ValidationItem] = []
    for assumption in ranked_assumptions:
        template = _template_for(assumption.category)
        items.append(
            ValidationItem(
                rank=assumption.rank,
                assumption_id=assumption.id,
                assumption_text=assumption.text,
                priority=priority_for(assumption.criticality),
                criticality=assumption.criticality,
                evidence_status=assumption.evidence_status,
                validation_method=template.method,
                test_question=_test_question(assumption.text),
                success_signal=template.success_signal,
                recommended_sample=template.recommended_sample,
                rationale=_rationale(assumption),
            )
        )
    return ValidationPlan(items=items)
