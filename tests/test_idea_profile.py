import re
import unittest

from models.reference_class import (
    UNRESOLVED_FIELD_ORDER,
    BusinessModel,
    CustomerType,
    IdeaProfile,
    ProductForm,
    UnresolvedField,
)
from services.idea_profile import INDUSTRY_TAGS, build_idea_profile

_KEYWORD_RE = re.compile(r"^[a-z0-9][a-z0-9.+\-]*( [a-z0-9][a-z0-9.+\-]*)?$")

_RICH_IDEA = (
    "AI-powered tutoring platform for college students.\n"
    "The platform generates personalized study plans, practice questions, "
    "and interview preparation material.\n"
    "Revenue model is monthly subscription."
)


class GuardTests(unittest.TestCase):
    def test_empty_input_raises(self):
        with self.assertRaises(ValueError):
            build_idea_profile("")

    def test_whitespace_only_input_raises(self):
        with self.assertRaises(ValueError):
            build_idea_profile("   \n\t ")

    def test_returns_idea_profile(self):
        self.assertIsInstance(build_idea_profile("a marketplace for freelancers"), IdeaProfile)

    def test_output_is_deterministic(self):
        first = build_idea_profile(_RICH_IDEA)
        second = build_idea_profile(_RICH_IDEA)
        self.assertEqual(first.model_dump(), second.model_dump())

    def test_raw_text_is_truncated_to_10k(self):
        profile = build_idea_profile("subscription tool for teams. " + "x" * 11000)
        self.assertEqual(len(profile.raw_text), 10_000)


class RichIdeaTests(unittest.TestCase):
    def setUp(self):
        self.profile = build_idea_profile(_RICH_IDEA)

    def test_industry(self):
        self.assertEqual(self.profile.industry, "edtech")

    def test_business_model(self):
        self.assertEqual(self.profile.business_model, BusinessModel.SUBSCRIPTION)

    def test_product_form_prefers_platform_over_app(self):
        self.assertEqual(self.profile.product_form, ProductForm.PLATFORM)

    def test_customer_type(self):
        self.assertEqual(self.profile.customer_type, CustomerType.CONSUMER)

    def test_customer_descriptor(self):
        self.assertEqual(self.profile.customer_descriptor, "college students")

    def test_problem_is_unresolved(self):
        self.assertEqual(self.profile.problem, "unspecified")

    def test_geography_is_unresolved(self):
        self.assertEqual(self.profile.geography, "unspecified")

    def test_unresolved_fields_are_exactly_problem_and_geography(self):
        self.assertEqual(
            self.profile.unresolved_fields,
            [UnresolvedField.PROBLEM, UnresolvedField.GEOGRAPHY],
        )

    def test_keywords_are_well_formed(self):
        kws = self.profile.keywords
        self.assertLessEqual(len(kws), 12)
        self.assertEqual(len(kws), len(set(kws)))
        for kw in kws:
            self.assertRegex(kw, _KEYWORD_RE)
        self.assertIn("tutoring", kws)


class KeywordBigramTests(unittest.TestCase):
    # 10 distinct one-off content words separated by "the", then an adjacent pair.
    _TEXT = (
        "alpha the beta the gamma the delta the epsilon the zeta the eta the "
        "theta the iota the kappa the lambda omega"
    )

    def setUp(self):
        self.keywords = build_idea_profile(self._TEXT).keywords

    def test_real_adjacent_pair_becomes_a_bigram(self):
        self.assertIn("lambda omega", self.keywords)

    def test_pair_adjacent_only_after_stopword_removal_is_not_a_bigram(self):
        # "kappa" (orig pos 18) and "lambda" (orig pos 20) are consecutive in the
        # filtered content list but not in the original stream.
        self.assertNotIn("kappa lambda", self.keywords)
        self.assertNotIn("iota kappa", self.keywords)

    def test_keyword_cap_is_respected(self):
        self.assertLessEqual(len(self.keywords), 12)


class IndustryTests(unittest.TestCase):
    def test_single_keyword_is_below_threshold(self):
        self.assertEqual(build_idea_profile("we process payments online").industry, "unspecified")

    def test_two_keywords_resolve_industry(self):
        self.assertEqual(
            build_idea_profile("a tool for payments and invoicing").industry, "fintech"
        )

    def test_tie_is_broken_by_map_order(self):
        # 2 edtech hits (course, students) vs 2 fintech hits (loan, credit) -> edtech first.
        profile = build_idea_profile(
            "an online course where students apply for a loan and a credit line"
        )
        self.assertEqual(profile.industry, "edtech")

    def test_industry_value_is_always_in_vocabulary(self):
        self.assertIn(build_idea_profile("something vague and novel here").industry, INDUSTRY_TAGS)


class ProductFormTests(unittest.TestCase):
    def test_platform_beats_app(self):
        self.assertEqual(
            build_idea_profile("a mobile app platform for teams").product_form,
            ProductForm.PLATFORM,
        )

    def test_plain_mobile_app(self):
        self.assertEqual(
            build_idea_profile("a simple mobile app to track water intake").product_form,
            ProductForm.APP,
        )

    def test_hardware(self):
        self.assertEqual(
            build_idea_profile("a wearable sensor device for athletes").product_form,
            ProductForm.HARDWARE,
        )


class BusinessModelTests(unittest.TestCase):
    def test_subscription(self):
        self.assertEqual(
            build_idea_profile("we charge a monthly subscription").business_model,
            BusinessModel.SUBSCRIPTION,
        )

    def test_freemium_when_free_and_upgrade_present(self):
        self.assertEqual(
            build_idea_profile(
                "monthly subscription with a free tier and an upgrade to premium"
            ).business_model,
            BusinessModel.FREEMIUM,
        )

    def test_freemium_direct_rule(self):
        self.assertEqual(
            build_idea_profile("a free tier and a free plan for everyone").business_model,
            BusinessModel.FREEMIUM,
        )

    def test_subscription_wins_tie_without_premium_upgrade(self):
        self.assertEqual(
            build_idea_profile(
                "a monthly subscription that also has a free tier"
            ).business_model,
            BusinessModel.SUBSCRIPTION,
        )


class CustomerTypeTests(unittest.TestCase):
    def test_developer_priority(self):
        self.assertEqual(
            build_idea_profile("an sdk for developers building payment apps").customer_type,
            CustomerType.DEVELOPER,
        )

    def test_business(self):
        self.assertEqual(
            build_idea_profile("a tool for enterprise sales teams").customer_type,
            CustomerType.BUSINESS,
        )

    def test_consumer(self):
        self.assertEqual(
            build_idea_profile("an app that helps consumers save money").customer_type,
            CustomerType.CONSUMER,
        )

    def test_tie_is_broken_by_first_occurrence(self):
        # "b2b" appears before "consumers" -> BUSINESS wins the equal-count tie.
        self.assertEqual(
            build_idea_profile("a b2b tool that consumers also love").customer_type,
            CustomerType.BUSINESS,
        )


class GeographyTests(unittest.TestCase):
    def test_specific_region(self):
        self.assertEqual(
            build_idea_profile("a fintech product. the main market is india").geography,
            "India",
        )

    def test_global(self):
        self.assertEqual(
            build_idea_profile("sold worldwide to anyone who wants it").geography, "Global"
        )

    def test_specific_region_beats_later_region(self):
        self.assertEqual(
            build_idea_profile("focused on the united states, expanding to india later").geography,
            "United States",
        )

    def test_unspecified(self):
        profile = build_idea_profile("a tool for small teams")
        self.assertEqual(profile.geography, "unspecified")
        self.assertIn(UnresolvedField.GEOGRAPHY, profile.unresolved_fields)


class DescriptorAndProblemTests(unittest.TestCase):
    def test_descriptor_falls_back_to_audience_noun(self):
        profile = build_idea_profile(
            "A study tool. Students use it every day. Students love it."
        )
        self.assertEqual(profile.customer_descriptor, "students")
        self.assertNotIn(UnresolvedField.CUSTOMER_DESCRIPTOR, profile.unresolved_fields)

    def test_problem_extracted_from_explicit_framing(self):
        profile = build_idea_profile(
            "The problem: freelancers waste hours chasing unpaid invoices every month."
        )
        self.assertTrue(profile.problem.startswith("freelancers waste hours"))
        self.assertNotIn(UnresolvedField.PROBLEM, profile.unresolved_fields)

    def test_problem_extracted_from_hard_to_phrasing(self):
        profile = build_idea_profile("It is hard to find affordable childcare nearby.")
        self.assertIn("affordable childcare", profile.problem)


class NothingResolvedTests(unittest.TestCase):
    def test_gibberish_marks_every_field_unresolved(self):
        profile = build_idea_profile("wubble flomp zonk quix nerd blorp")
        self.assertEqual(profile.unresolved_fields, list(UNRESOLVED_FIELD_ORDER))
        self.assertEqual(profile.industry, "unspecified")
        self.assertEqual(profile.customer_type, CustomerType.UNKNOWN)
        self.assertEqual(profile.product_form, ProductForm.UNKNOWN)
        self.assertEqual(profile.business_model, BusinessModel.UNKNOWN)

    def test_resolution_biconditional_holds_on_built_profile(self):
        profile = build_idea_profile("wubble flomp zonk quix nerd blorp")
        marked = set(profile.unresolved_fields)
        self.assertEqual(
            profile.industry == "unspecified", UnresolvedField.INDUSTRY in marked
        )
        self.assertEqual(
            profile.geography == "unspecified", UnresolvedField.GEOGRAPHY in marked
        )


if __name__ == "__main__":
    unittest.main()
