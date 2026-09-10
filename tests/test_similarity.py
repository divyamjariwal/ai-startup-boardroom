import unittest

from pydantic import ValidationError

from models.reference_class import (
    FORBIDDEN_DESCRIPTIVE_PHRASES,
    SIMILARITY_DIVERGENT_THRESHOLD,
    SIMILARITY_MATCH_THRESHOLD,
    SIMILARITY_WEIGHTS,
    UNRESOLVED_FIELD_ORDER,
    BusinessModel,
    CandidateProfile,
    CustomerType,
    DimensionScore,
    IdeaProfile,
    ProductForm,
    SimilarityBreakdown,
    SimilarityDimension,
    UnresolvedField,
)
from services.idea_profile import INDUSTRY_TAGS, tokenize
from services.similarity import (
    _BUSINESS_MODEL_RELATED,
    _INDUSTRY_SIBLINGS,
    _PRODUCT_FORM_ADJACENCY,
    is_relevant,
    score_similarity,
)

_UNRESOLVED_FOR = {
    "customer_type": (CustomerType.UNKNOWN, UnresolvedField.CUSTOMER_TYPE),
    "customer_descriptor": ("unspecified", UnresolvedField.CUSTOMER_DESCRIPTOR),
    "problem": ("unspecified", UnresolvedField.PROBLEM),
    "product_form": (ProductForm.UNKNOWN, UnresolvedField.PRODUCT_FORM),
    "business_model": (BusinessModel.UNKNOWN, UnresolvedField.BUSINESS_MODEL),
    "industry": ("unspecified", UnresolvedField.INDUSTRY),
    "geography": ("unspecified", UnresolvedField.GEOGRAPHY),
}


def _idea(**kw) -> IdeaProfile:
    base = dict(
        customer_type=CustomerType.CONSUMER,
        customer_descriptor="college students",
        problem="students struggle to find affordable exam preparation",
        product_form=ProductForm.APP,
        business_model=BusinessModel.SUBSCRIPTION,
        industry="edtech",
        geography="United States",
        keywords=["tutoring", "exam", "prep"],
    )
    base.update(kw)
    marked = {
        field
        for name, (sentinel, field) in _UNRESOLVED_FOR.items()
        if base[name] == sentinel or base[name] is sentinel
    }
    base.setdefault(
        "unresolved_fields", [f for f in UNRESOLVED_FIELD_ORDER if f in marked]
    )
    base.setdefault("raw_text", "constructed idea profile for similarity tests")
    return IdeaProfile(**base)


def _cand(**kw) -> CandidateProfile:
    base = dict(
        name="Comparable Co",
        one_liner="on-demand exam prep and study help for students",
        industry="edtech",
        geography="United States",
        business_model=BusinessModel.SUBSCRIPTION,
        product_form=ProductForm.APP,
        customer_type=CustomerType.CONSUMER,
        customer_descriptor="students",
    )
    base.update(kw)
    return CandidateProfile(**base)


def _dim(breakdown: SimilarityBreakdown, dimension: SimilarityDimension) -> DimensionScore:
    return next(d for d in breakdown.dimensions if d.dimension is dimension)


def _score(idea: IdeaProfile, cand: CandidateProfile, dimension: SimilarityDimension) -> float:
    return _dim(score_similarity(idea, cand), dimension).score


def _uniform_breakdown(value: float) -> SimilarityBreakdown:
    dims = [
        DimensionScore(
            dimension=d,
            score=value,
            weight=SIMILARITY_WEIGHTS[d],
            weighted_score=value * SIMILARITY_WEIGHTS[d],
            basis="constructed",
        )
        for d in SimilarityDimension
    ]
    return SimilarityBreakdown(
        dimensions=dims,
        total=round(100 * sum(d.weighted_score for d in dims)),
        matched_dimensions=[d.dimension for d in dims if d.score >= SIMILARITY_MATCH_THRESHOLD],
        divergent_dimensions=[
            d.dimension for d in dims if d.score <= SIMILARITY_DIVERGENT_THRESHOLD
        ],
        rationale="constructed uniform breakdown",
    )


# --------------------------------------------------------------------------- #
# INDUSTRY
# --------------------------------------------------------------------------- #
class IndustryDimensionTests(unittest.TestCase):
    def test_exact(self):
        self.assertEqual(
            _score(_idea(industry="edtech"), _cand(industry="edtech"), SimilarityDimension.INDUSTRY),
            1.0,
        )

    def test_sibling(self):
        self.assertEqual(
            _score(_idea(industry="fintech"), _cand(industry="insurtech"), SimilarityDimension.INDUSTRY),
            0.5,
        )

    def test_sibling_is_symmetric(self):
        self.assertEqual(
            _score(_idea(industry="insurtech"), _cand(industry="fintech"), SimilarityDimension.INDUSTRY),
            0.5,
        )

    def test_unrelated(self):
        self.assertEqual(
            _score(_idea(industry="edtech"), _cand(industry="gaming"), SimilarityDimension.INDUSTRY),
            0.0,
        )

    def test_idea_unspecified(self):
        self.assertEqual(
            _score(_idea(industry="unspecified"), _cand(industry="edtech"), SimilarityDimension.INDUSTRY),
            0.3,
        )

    def test_candidate_unspecified(self):
        self.assertEqual(
            _score(_idea(industry="edtech"), _cand(industry="unspecified"), SimilarityDimension.INDUSTRY),
            0.3,
        )


# --------------------------------------------------------------------------- #
# PRODUCT_FORM
# --------------------------------------------------------------------------- #
class ProductFormDimensionTests(unittest.TestCase):
    def test_exact(self):
        self.assertEqual(
            _score(_idea(product_form=ProductForm.SAAS), _cand(product_form=ProductForm.SAAS), SimilarityDimension.PRODUCT_FORM),
            1.0,
        )

    def test_adjacent(self):
        for a, b in ((ProductForm.APP, ProductForm.SAAS), (ProductForm.SAAS, ProductForm.PLATFORM), (ProductForm.MARKETPLACE, ProductForm.PLATFORM)):
            self.assertEqual(
                _score(_idea(product_form=a), _cand(product_form=b), SimilarityDimension.PRODUCT_FORM), 0.5, (a, b)
            )

    def test_adjacent_is_symmetric(self):
        self.assertEqual(
            _score(_idea(product_form=ProductForm.SAAS), _cand(product_form=ProductForm.APP), SimilarityDimension.PRODUCT_FORM),
            0.5,
        )

    def test_mismatch(self):
        self.assertEqual(
            _score(_idea(product_form=ProductForm.HARDWARE), _cand(product_form=ProductForm.CONTENT), SimilarityDimension.PRODUCT_FORM),
            0.1,
        )

    def test_unknown_either_side(self):
        self.assertEqual(
            _score(_idea(product_form=ProductForm.UNKNOWN), _cand(product_form=ProductForm.APP), SimilarityDimension.PRODUCT_FORM),
            0.3,
        )
        self.assertEqual(
            _score(_idea(product_form=ProductForm.APP), _cand(product_form=ProductForm.UNKNOWN), SimilarityDimension.PRODUCT_FORM),
            0.3,
        )


# --------------------------------------------------------------------------- #
# BUSINESS_MODEL
# --------------------------------------------------------------------------- #
class BusinessModelDimensionTests(unittest.TestCase):
    def test_exact(self):
        self.assertEqual(
            _score(_idea(business_model=BusinessModel.SUBSCRIPTION), _cand(business_model=BusinessModel.SUBSCRIPTION), SimilarityDimension.BUSINESS_MODEL),
            1.0,
        )

    def test_related(self):
        for a, b in (
            (BusinessModel.SUBSCRIPTION, BusinessModel.FREEMIUM),
            (BusinessModel.TRANSACTIONAL, BusinessModel.MARKETPLACE),
            (BusinessModel.ADVERTISING, BusinessModel.FREEMIUM),
            (BusinessModel.SUBSCRIPTION, BusinessModel.LICENSING),
        ):
            self.assertEqual(
                _score(_idea(business_model=a), _cand(business_model=b), SimilarityDimension.BUSINESS_MODEL), 0.6, (a, b)
            )

    def test_related_is_symmetric(self):
        self.assertEqual(
            _score(_idea(business_model=BusinessModel.FREEMIUM), _cand(business_model=BusinessModel.SUBSCRIPTION), SimilarityDimension.BUSINESS_MODEL),
            0.6,
        )

    def test_mismatch(self):
        self.assertEqual(
            _score(_idea(business_model=BusinessModel.ADVERTISING), _cand(business_model=BusinessModel.HARDWARE), SimilarityDimension.BUSINESS_MODEL),
            0.1,
        )

    def test_unknown_either_side(self):
        self.assertEqual(
            _score(_idea(business_model=BusinessModel.UNKNOWN), _cand(business_model=BusinessModel.SUBSCRIPTION), SimilarityDimension.BUSINESS_MODEL),
            0.3,
        )


# --------------------------------------------------------------------------- #
# CUSTOMER
# --------------------------------------------------------------------------- #
class CustomerDimensionTests(unittest.TestCase):
    def test_exact_segment_on_descriptor_overlap(self):
        self.assertEqual(
            _score(
                _idea(customer_type=CustomerType.CONSUMER, customer_descriptor="college students"),
                _cand(customer_type=CustomerType.CONSUMER, customer_descriptor="students"),
                SimilarityDimension.CUSTOMER,
            ),
            1.0,
        )

    def test_same_type_without_descriptor_overlap(self):
        self.assertEqual(
            _score(
                _idea(customer_type=CustomerType.BUSINESS, customer_descriptor="retail buyers"),
                _cand(customer_type=CustomerType.BUSINESS, customer_descriptor="software vendors"),
                SimilarityDimension.CUSTOMER,
            ),
            0.5,
        )

    def test_same_type_with_missing_candidate_descriptor(self):
        self.assertEqual(
            _score(
                _idea(customer_type=CustomerType.CONSUMER, customer_descriptor="college students"),
                _cand(customer_type=CustomerType.CONSUMER, customer_descriptor=None),
                SimilarityDimension.CUSTOMER,
            ),
            0.5,
        )

    def test_same_type_with_unspecified_idea_descriptor(self):
        self.assertEqual(
            _score(
                _idea(customer_type=CustomerType.CONSUMER, customer_descriptor="unspecified"),
                _cand(customer_type=CustomerType.CONSUMER, customer_descriptor="students"),
                SimilarityDimension.CUSTOMER,
            ),
            0.5,
        )

    def test_conflicting_consumer_vs_business(self):
        self.assertEqual(
            _score(
                _idea(customer_type=CustomerType.CONSUMER),
                _cand(customer_type=CustomerType.BUSINESS),
                SimilarityDimension.CUSTOMER,
            ),
            0.0,
        )

    def test_conflicting_is_symmetric(self):
        self.assertEqual(
            _score(
                _idea(customer_type=CustomerType.BUSINESS, customer_descriptor="teams"),
                _cand(customer_type=CustomerType.CONSUMER),
                SimilarityDimension.CUSTOMER,
            ),
            0.0,
        )

    def test_conflicting_consumer_vs_developer(self):
        self.assertEqual(
            _score(
                _idea(customer_type=CustomerType.CONSUMER),
                _cand(customer_type=CustomerType.DEVELOPER),
                SimilarityDimension.CUSTOMER,
            ),
            0.0,
        )

    def test_related_org_buyers(self):
        for a, b in (
            (CustomerType.BUSINESS, CustomerType.DEVELOPER),
            (CustomerType.DEVELOPER, CustomerType.PUBLIC_SECTOR),
            (CustomerType.BUSINESS, CustomerType.PUBLIC_SECTOR),
        ):
            self.assertEqual(
                _score(_idea(customer_type=a, customer_descriptor="teams"), _cand(customer_type=b), SimilarityDimension.CUSTOMER),
                0.3,
                (a, b),
            )

    def test_unknown_either_side(self):
        self.assertEqual(
            _score(_idea(customer_type=CustomerType.UNKNOWN), _cand(customer_type=CustomerType.CONSUMER), SimilarityDimension.CUSTOMER),
            0.3,
        )
        self.assertEqual(
            _score(_idea(customer_type=CustomerType.CONSUMER), _cand(customer_type=CustomerType.UNKNOWN), SimilarityDimension.CUSTOMER),
            0.3,
        )


# --------------------------------------------------------------------------- #
# GEOGRAPHY
# --------------------------------------------------------------------------- #
class GeographyDimensionTests(unittest.TestCase):
    def test_same_region(self):
        self.assertEqual(
            _score(_idea(geography="United States"), _cand(geography="United States"), SimilarityDimension.GEOGRAPHY),
            1.0,
        )

    def test_both_global(self):
        self.assertEqual(
            _score(_idea(geography="Global"), _cand(geography="Global"), SimilarityDimension.GEOGRAPHY),
            0.7,
        )

    def test_idea_unspecified(self):
        self.assertEqual(
            _score(_idea(geography="unspecified"), _cand(geography="India"), SimilarityDimension.GEOGRAPHY),
            0.5,
        )

    def test_candidate_none_is_unspecified(self):
        self.assertEqual(
            _score(_idea(geography="India"), _cand(geography=None), SimilarityDimension.GEOGRAPHY),
            0.5,
        )

    def test_candidate_unspecified_string(self):
        self.assertEqual(
            _score(_idea(geography="India"), _cand(geography="unspecified"), SimilarityDimension.GEOGRAPHY),
            0.5,
        )

    def test_global_vs_specific_region(self):
        self.assertEqual(
            _score(_idea(geography="Global"), _cand(geography="India"), SimilarityDimension.GEOGRAPHY),
            0.5,
        )
        self.assertEqual(
            _score(_idea(geography="India"), _cand(geography="Global"), SimilarityDimension.GEOGRAPHY),
            0.5,
        )

    def test_different_regions(self):
        self.assertEqual(
            _score(_idea(geography="United States"), _cand(geography="India"), SimilarityDimension.GEOGRAPHY),
            0.3,
        )


# --------------------------------------------------------------------------- #
# PROBLEM
# --------------------------------------------------------------------------- #
class ProblemDimensionTests(unittest.TestCase):
    def _syn(self, n: int) -> list[str]:
        return [f"term{i:02d}" for i in range(n)]

    def test_full_overlap(self):
        idea = _idea(keywords=self._syn(5), problem="unspecified")
        cand = _cand(one_liner="term00 term01 term02 term03 term04")
        self.assertEqual(_score(idea, cand, SimilarityDimension.PROBLEM), 1.0)

    def test_band_070(self):
        idea = _idea(keywords=self._syn(5), problem="unspecified")
        cand = _cand(one_liner="term00 term01 zzz nothing here")  # 2/5 = 0.40
        self.assertEqual(_score(idea, cand, SimilarityDimension.PROBLEM), 0.7)

    def test_band_050_at_boundary(self):
        idea = _idea(keywords=self._syn(20), problem="unspecified")
        cand = _cand(one_liner="term00 term01 term02 zzz zzz")  # 3/20 = 0.15
        self.assertEqual(_score(idea, cand, SimilarityDimension.PROBLEM), 0.5)

    def test_small_overlap_below_first_band(self):
        idea = _idea(keywords=self._syn(20), problem="unspecified")
        cand = _cand(one_liner="term00 term01 zzz zzz zzz")  # 2/20 = 0.10
        self.assertEqual(_score(idea, cand, SimilarityDimension.PROBLEM), 0.3)

    def test_zero_overlap(self):
        idea = _idea(keywords=self._syn(5), problem="unspecified")
        cand = _cand(one_liner="completely unrelated wording about widgets")
        self.assertEqual(_score(idea, cand, SimilarityDimension.PROBLEM), 0.1)

    def test_insufficient_idea_text(self):
        idea = _idea(keywords=[], problem="unspecified")
        cand = _cand(one_liner="on-demand tutoring for students")
        self.assertEqual(_score(idea, cand, SimilarityDimension.PROBLEM), 0.3)

    def test_insufficient_candidate_text(self):
        idea = _idea(keywords=self._syn(5), problem="unspecified")
        cand = _cand(one_liner="a b c")  # all tokens below the length band
        self.assertEqual(_score(idea, cand, SimilarityDimension.PROBLEM), 0.3)

    def test_problem_text_falls_back_to_keywords_when_unspecified(self):
        idea = _idea(keywords=["alpha", "beta"], problem="unspecified")
        cand = _cand(one_liner="alpha beta")
        self.assertEqual(_score(idea, cand, SimilarityDimension.PROBLEM), 1.0)

    def test_problem_text_is_used_when_present(self):
        idea = _idea(
            keywords=["zzz"],
            problem="freelancers waste hours chasing unpaid invoices monthly",
        )
        cand = _cand(one_liner="tool for freelancers who chase unpaid invoices")
        self.assertGreaterEqual(_score(idea, cand, SimilarityDimension.PROBLEM), 0.5)


# --------------------------------------------------------------------------- #
# Aggregation, weights, matched/divergent
# --------------------------------------------------------------------------- #
class AggregationTests(unittest.TestCase):
    def test_dimension_order_and_completeness(self):
        breakdown = score_similarity(_idea(), _cand())
        self.assertEqual(
            [d.dimension for d in breakdown.dimensions], list(SimilarityDimension)
        )

    def test_weighted_score_is_raw_score_times_weight(self):
        breakdown = score_similarity(_idea(), _cand())
        for d in breakdown.dimensions:
            self.assertEqual(d.weight, SIMILARITY_WEIGHTS[d.dimension])
            self.assertEqual(d.weighted_score, d.score * d.weight)

    def test_total_uses_the_aggregation_rule(self):
        breakdown = score_similarity(_idea(), _cand())
        self.assertEqual(
            breakdown.total,
            round(100 * sum(d.weighted_score for d in breakdown.dimensions)),
        )

    def test_identical_profiles_score_100_and_all_matched(self):
        idea = _idea(
            keywords=["alpha", "beta"],
            problem="unspecified",
            geography="India",
            customer_descriptor="college students",
        )
        cand = _cand(
            one_liner="alpha beta",
            industry="edtech",
            geography="India",
            business_model=BusinessModel.SUBSCRIPTION,
            product_form=ProductForm.APP,
            customer_type=CustomerType.CONSUMER,
            customer_descriptor="college students",
        )
        breakdown = score_similarity(idea, cand)
        self.assertEqual(breakdown.total, 100)
        self.assertEqual(breakdown.matched_dimensions, list(SimilarityDimension))
        self.assertEqual(breakdown.divergent_dimensions, [])

    def test_matched_and_divergent_partitions(self):
        idea = _idea(
            keywords=["term00", "term01", "term02", "term03", "term04"],
            problem="unspecified",
            product_form=ProductForm.APP,
            geography="United States",
        )
        cand = _cand(
            one_liner="term00 term01 zzz zzz zzz",  # 2/5 -> problem 0.70 (matched)
            industry="edtech",  # matched 1.0
            business_model=BusinessModel.SUBSCRIPTION,  # matched 1.0
            customer_type=CustomerType.CONSUMER,
            customer_descriptor="students",  # matched 1.0
            product_form=ProductForm.HARDWARE,  # divergent 0.1
            geography="India",  # divergent 0.3
        )
        breakdown = score_similarity(idea, cand)
        self.assertEqual(
            breakdown.matched_dimensions,
            [
                SimilarityDimension.PROBLEM,
                SimilarityDimension.CUSTOMER,
                SimilarityDimension.INDUSTRY,
                SimilarityDimension.BUSINESS_MODEL,
            ],
        )
        self.assertEqual(
            breakdown.divergent_dimensions,
            [SimilarityDimension.PRODUCT_FORM, SimilarityDimension.GEOGRAPHY],
        )

    def test_returns_valid_similarity_breakdown(self):
        self.assertIsInstance(score_similarity(_idea(), _cand()), SimilarityBreakdown)


# --------------------------------------------------------------------------- #
# Relevance threshold
# --------------------------------------------------------------------------- #
class RelevanceTests(unittest.TestCase):
    def test_uniform_45_is_relevant(self):
        breakdown = _uniform_breakdown(0.45)
        self.assertEqual(breakdown.total, 45)
        self.assertTrue(is_relevant(breakdown))

    def test_uniform_44_is_not_relevant(self):
        breakdown = _uniform_breakdown(0.44)
        self.assertEqual(breakdown.total, 44)
        self.assertFalse(is_relevant(breakdown))

    def test_near_identical_candidate_is_relevant(self):
        breakdown = score_similarity(_idea(), _cand())
        self.assertGreaterEqual(breakdown.total, 80)
        self.assertTrue(is_relevant(breakdown))

    def test_no_information_candidate_is_not_relevant(self):
        idea = _idea(
            customer_type=CustomerType.UNKNOWN,
            customer_descriptor="unspecified",
            problem="unspecified",
            product_form=ProductForm.UNKNOWN,
            business_model=BusinessModel.UNKNOWN,
            industry="unspecified",
            geography="unspecified",
            keywords=[],
        )
        cand = CandidateProfile(name="Mystery", one_liner="a company")
        breakdown = score_similarity(idea, cand)
        self.assertEqual(breakdown.total, 31)
        self.assertFalse(is_relevant(breakdown))


# --------------------------------------------------------------------------- #
# Determinism, purity, output text
# --------------------------------------------------------------------------- #
class DeterminismAndOutputTests(unittest.TestCase):
    def test_repeated_calls_are_identical(self):
        idea, cand = _idea(), _cand()
        first = score_similarity(idea, cand)
        second = score_similarity(idea, cand)
        self.assertEqual(first.model_dump(), second.model_dump())

    def test_inputs_are_not_mutated(self):
        idea, cand = _idea(), _cand()
        before_idea, before_cand = idea.model_dump(), cand.model_dump()
        score_similarity(idea, cand)
        self.assertEqual(idea.model_dump(), before_idea)
        self.assertEqual(cand.model_dump(), before_cand)

    def test_basis_length_within_bound(self):
        breakdown = score_similarity(_idea(), _cand())
        for d in breakdown.dimensions:
            self.assertTrue(1 <= len(d.basis) <= 200)

    def test_rationale_length_within_bound(self):
        breakdown = score_similarity(_idea(), _cand())
        self.assertTrue(1 <= len(breakdown.rationale) <= 600)

    def test_rationale_has_no_forbidden_descriptive_language(self):
        breakdown = score_similarity(_idea(), _cand())
        lowered = breakdown.rationale.lower()
        for phrase in FORBIDDEN_DESCRIPTIVE_PHRASES:
            self.assertNotIn(phrase, lowered)

    def test_candidate_name_with_forbidden_substring_does_not_break_scoring(self):
        # A real company ("Guaranteed Rate") would trip the 4A rationale guard if
        # the name were interpolated; score_similarity must stay safe.
        breakdown = score_similarity(_idea(), _cand(name="Guaranteed Rate"))
        self.assertIsInstance(breakdown, SimilarityBreakdown)
        self.assertNotIn("guaranteed", breakdown.rationale.lower())


# --------------------------------------------------------------------------- #
# CandidateProfile model
# --------------------------------------------------------------------------- #
class CandidateProfileTests(unittest.TestCase):
    def test_minimal_defaults(self):
        cp = CandidateProfile(name="X", one_liner="y")
        self.assertEqual(cp.industry, "unspecified")
        self.assertIsNone(cp.geography)
        self.assertIs(cp.business_model, BusinessModel.UNKNOWN)
        self.assertIs(cp.product_form, ProductForm.UNKNOWN)
        self.assertIs(cp.customer_type, CustomerType.UNKNOWN)
        self.assertIsNone(cp.customer_descriptor)

    def test_extra_fields_forbidden(self):
        with self.assertRaises(ValidationError):
            CandidateProfile(name="X", one_liner="y", evidence_ids=["E-001"])

    def test_empty_one_liner_rejected(self):
        with self.assertRaises(ValidationError):
            CandidateProfile(name="X", one_liner="")

    def test_empty_name_rejected(self):
        with self.assertRaises(ValidationError):
            CandidateProfile(name="", one_liner="y")

    def test_strict_rejects_non_enum_int(self):
        with self.assertRaises(ValidationError):
            CandidateProfile(name="X", one_liner="y", business_model=3)


# --------------------------------------------------------------------------- #
# Invalid inputs to the engine
# --------------------------------------------------------------------------- #
class InvalidInputTests(unittest.TestCase):
    def test_non_profile_idea_raises(self):
        with self.assertRaises((AttributeError, TypeError)):
            score_similarity("not an idea profile", _cand())

    def test_non_profile_candidate_raises(self):
        with self.assertRaises((AttributeError, TypeError)):
            score_similarity(_idea(), {"name": "x", "one_liner": "y"})


# --------------------------------------------------------------------------- #
# Policy tables reference only the real taxonomy
# --------------------------------------------------------------------------- #
class PolicyTableTests(unittest.TestCase):
    def test_industry_siblings_use_real_tags(self):
        for pair in _INDUSTRY_SIBLINGS:
            self.assertEqual(len(pair), 2)
            for tag in pair:
                self.assertIn(tag, INDUSTRY_TAGS)
                self.assertNotEqual(tag, "unspecified")

    def test_product_form_adjacency_uses_real_members(self):
        for pair in _PRODUCT_FORM_ADJACENCY:
            self.assertEqual(len(pair), 2)
            for form in pair:
                self.assertIsInstance(form, ProductForm)
                self.assertIsNot(form, ProductForm.UNKNOWN)

    def test_business_model_related_uses_real_members(self):
        for pair in _BUSINESS_MODEL_RELATED:
            self.assertEqual(len(pair), 2)
            for model in pair:
                self.assertIsInstance(model, BusinessModel)
                self.assertIsNot(model, BusinessModel.UNKNOWN)


class TokenizeTests(unittest.TestCase):
    def test_returns_list_of_lowercase_tokens(self):
        self.assertEqual(tokenize("AI-powered Study Plans"), ["ai-powered", "study", "plans"])

    def test_empty_string(self):
        self.assertEqual(tokenize(""), [])


if __name__ == "__main__":
    unittest.main()
