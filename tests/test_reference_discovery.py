import unittest

from pydantic import HttpUrl, ValidationError

from models.reference_class import (
    SIMILARITY_INCLUSION_THRESHOLD,
    BusinessModel,
    CandidateProfile,
    CustomerType,
    DropReason,
    ProductForm,
    ReferenceClassStatus,
)
from services.idea_profile import GEO_REGION_LABELS, build_idea_profile
from services.research import NormalizedSearchResult, ResearchProvider, ResearchProviderUnavailable
from services.reference_discovery import (
    MAX_DISCOVERY_QUERIES,
    CandidateExtraction,
    DiscoveryResult,
    ExtractedCandidate,
    _dedupe_key,
    _normalize_enum,
    _normalize_geography,
    _normalize_industry,
    discover_reference_class,
    discovery_queries,
)
from services.similarity import is_relevant, score_similarity

IDEA_TEXT = (
    "AI tutoring app for college students. Monthly subscription. "
    "Practice questions and personalized study plans for exam preparation."
)


def _idea(text: str = IDEA_TEXT):
    return build_idea_profile(text)


def _result(url: str, title: str = "Article", excerpt: str = "some text about a startup", score: float = 0.6):
    return NormalizedSearchResult(
        title=title, url=HttpUrl(url), excerpt=excerpt, relevance_score=score, publication_date=None
    )


class _FakeProvider(ResearchProvider):
    name = "fake"

    def __init__(self, batches, fail_calls=frozenset()):
        self._batches = list(batches)
        self._fail_calls = set(fail_calls)
        self.calls: list[str] = []

    def search(self, query: str, max_results: int):
        index = len(self.calls)
        self.calls.append(query)
        if index in self._fail_calls:
            raise ResearchProviderUnavailable("fake failure")
        return self._batches[index] if index < len(self._batches) else []


def _stub(candidates):
    def _extract(idea, evidence):
        return CandidateExtraction(candidates=list(candidates))

    return _extract


def _raising_stub(exc=RuntimeError("llm down")):
    def _extract(idea, evidence):
        raise exc

    return _extract


def _relevant_candidate(**kw):
    base = dict(
        name="Chegg",
        one_liner="tutoring and practice questions for college students on a monthly subscription",
        industry="edtech",
        geography=None,
        business_model="subscription",
        product_form="app",
        customer_type="consumer",
        customer_descriptor="college students",
        supporting_evidence_ids=["E-001"],
    )
    base.update(kw)
    return ExtractedCandidate(**base)


# --------------------------------------------------------------------------- #
# discovery_queries
# --------------------------------------------------------------------------- #
class DiscoveryQueriesTests(unittest.TestCase):
    def test_two_non_empty_distinct_queries(self):
        queries = discovery_queries(_idea())
        self.assertEqual(len(queries), MAX_DISCOVERY_QUERIES)
        self.assertTrue(all(q.strip() for q in queries))
        self.assertNotEqual(queries[0].lower(), queries[1].lower())

    def test_second_query_mentions_resolved_industry(self):
        self.assertIn("edtech", discovery_queries(_idea())[1])

    def test_degenerate_idea_still_yields_two_queries(self):
        queries = discovery_queries(_idea("wubble flomp zonk quix nerd blorp"))
        self.assertEqual(len(queries), 2)
        self.assertTrue(all(q.strip() for q in queries))
        self.assertNotEqual(queries[0].lower(), queries[1].lower())

    def test_queries_are_deterministic(self):
        idea = _idea()
        self.assertEqual(discovery_queries(idea), discovery_queries(idea))


# --------------------------------------------------------------------------- #
# provider missing
# --------------------------------------------------------------------------- #
class NoProviderTests(unittest.TestCase):
    def test_no_provider_returns_unavailable(self):
        # No TAVILY_API_KEY in the test env -> configured_provider() is None.
        result = discover_reference_class(_idea())
        self.assertEqual(result.status, ReferenceClassStatus.UNAVAILABLE_NO_PROVIDER)
        self.assertEqual(result.candidates, [])
        self.assertEqual(result.search_count, 0)
        self.assertEqual(result.llm_calls, 0)
        self.assertEqual(result.evidence_store.list(), [])

    def test_no_provider_result_validates(self):
        self.assertIsInstance(discover_reference_class(_idea()), DiscoveryResult)


# --------------------------------------------------------------------------- #
# happy path + traceability
# --------------------------------------------------------------------------- #
class HappyPathTests(unittest.TestCase):
    def _run(self, extracted):
        provider = _FakeProvider([[_result("https://ex.com/a", "Chegg raises", "Chegg tutoring for students")], []])
        return discover_reference_class(_idea(), provider=provider, extractor=_stub(extracted))

    def test_relevant_candidate_is_kept(self):
        result = self._run([_relevant_candidate()])
        self.assertEqual(result.status, ReferenceClassStatus.AVAILABLE)
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(result.candidates[0].name, "Chegg")
        self.assertTrue(result.candidates[0].is_relevant)
        self.assertTrue(result.candidates[0].is_company_verified)

    def test_search_and_llm_counts(self):
        result = self._run([_relevant_candidate()])
        self.assertEqual(result.search_count, 2)
        self.assertEqual(result.llm_calls, 1)

    def test_candidate_is_traceable_to_evidence_source(self):
        result = self._run([_relevant_candidate()])
        candidate = result.candidates[0]
        self.assertEqual(candidate.evidence_ids, ["E-001"])
        evidence = result.evidence_store.get("E-001")
        self.assertIsNotNone(evidence)
        self.assertEqual(str(evidence.source_url), "https://ex.com/a")

    def test_relevance_decision_matches_4b_contract(self):
        result = self._run([_relevant_candidate()])
        candidate = result.candidates[0]
        profile = CandidateProfile(
            name=candidate.name,
            one_liner=candidate.one_liner,
            industry=candidate.industry,
            geography=candidate.geography,
            business_model=candidate.business_model,
            product_form=candidate.product_form,
            customer_type=candidate.customer_type,
            customer_descriptor=candidate.customer_descriptor,
        )
        self.assertEqual(
            candidate.is_relevant, is_relevant(score_similarity(result.idea_profile, profile))
        )

    def test_irrelevant_candidate_is_dropped_with_reason(self):
        raw = ExtractedCandidate(
            name="LubeCo",
            one_liner="industrial lubricant distributor for heavy machinery",
            industry="unknown",
            business_model="unknown",
            product_form="unknown",
            customer_type="unknown",
            supporting_evidence_ids=["E-001"],
        )
        result = self._run([raw])
        self.assertEqual(result.candidates, [])
        self.assertEqual(len(result.dropped), 1)
        self.assertEqual(result.dropped[0].reason, DropReason.INSUFFICIENT_RELEVANCE)
        self.assertEqual(result.dropped[0].evidence_ids, ["E-001"])
        self.assertEqual(result.status, ReferenceClassStatus.UNAVAILABLE_NO_MATCHES)

    def test_mixed_kept_and_dropped(self):
        keep = _relevant_candidate()
        drop = ExtractedCandidate(
            name="LubeCo", one_liner="industrial lubricant distributor", industry="unknown",
            business_model="unknown", product_form="unknown", customer_type="unknown",
            supporting_evidence_ids=["E-001"],
        )
        result = self._run([keep, drop])
        self.assertEqual([c.name for c in result.candidates], ["Chegg"])
        self.assertEqual([d.reason for d in result.dropped], [DropReason.INSUFFICIENT_RELEVANCE])
        self.assertEqual(result.status, ReferenceClassStatus.AVAILABLE)


# --------------------------------------------------------------------------- #
# evidence handling
# --------------------------------------------------------------------------- #
class EvidenceHandlingTests(unittest.TestCase):
    def test_duplicate_urls_collapse_to_one_evidence(self):
        provider = _FakeProvider(
            [
                [_result("https://ex.com/a", "A"), _result("https://ex.com/a", "A dup")],
                [],
            ]
        )
        result = discover_reference_class(
            _idea(), provider=provider, extractor=_stub([_relevant_candidate()])
        )
        self.assertEqual(len(result.evidence_store.list()), 1)

    def test_candidate_citing_only_unknown_evidence_is_not_verified(self):
        provider = _FakeProvider([[_result("https://ex.com/a", "A")], []])
        raw = _relevant_candidate(supporting_evidence_ids=["E-099"])
        result = discover_reference_class(_idea(), provider=provider, extractor=_stub([raw]))
        self.assertEqual(result.candidates, [])
        self.assertEqual(result.dropped[0].reason, DropReason.NOT_VERIFIED_AS_COMPANY)

    def test_unknown_evidence_ids_are_filtered_out(self):
        provider = _FakeProvider([[_result("https://ex.com/a", "A")], []])
        raw = _relevant_candidate(supporting_evidence_ids=["E-099", "E-001", "E-001"])
        result = discover_reference_class(_idea(), provider=provider, extractor=_stub([raw]))
        self.assertEqual(result.candidates[0].evidence_ids, ["E-001"])

    def test_missing_one_liner_falls_back_to_excerpt(self):
        provider = _FakeProvider(
            [[_result("https://ex.com/a", "Chegg", "Chegg offers tutoring and practice tests for college students")], []]
        )
        raw = _relevant_candidate(one_liner="")
        result = discover_reference_class(_idea(), provider=provider, extractor=_stub([raw]))
        self.assertEqual(len(result.candidates), 1)
        self.assertTrue(result.candidates[0].one_liner.startswith("Chegg offers tutoring"))
        self.assertLessEqual(len(result.candidates[0].one_liner), 200)


# --------------------------------------------------------------------------- #
# duplicates
# --------------------------------------------------------------------------- #
class DuplicateTests(unittest.TestCase):
    def test_same_name_deduped(self):
        provider = _FakeProvider([[_result("https://ex.com/a", "A")], []])
        first = _relevant_candidate(name="Chegg")
        second = _relevant_candidate(name="Chegg Inc.")
        result = discover_reference_class(_idea(), provider=provider, extractor=_stub([first, second]))
        self.assertEqual(len(result.candidates), 1)
        self.assertEqual(len(result.dropped), 1)
        self.assertEqual(result.dropped[0].reason, DropReason.DUPLICATE)
        self.assertEqual(result.dropped[0].merged_into, "Chegg")

    def test_dedupe_key_is_suffix_and_case_insensitive(self):
        self.assertEqual(_dedupe_key("Chegg Inc."), _dedupe_key("chegg"))
        self.assertEqual(_dedupe_key("Acme Ltd"), _dedupe_key("ACME"))


# --------------------------------------------------------------------------- #
# provider / extractor failures
# --------------------------------------------------------------------------- #
class FailureTests(unittest.TestCase):
    def test_one_query_fails_yields_partial(self):
        # call 0 fails, call 1 returns the evidence.
        provider = _FakeProvider([[], [_result("https://ex.com/a", "A")]], fail_calls={0})
        result = discover_reference_class(
            _idea(), provider=provider, extractor=_stub([_relevant_candidate()])
        )
        self.assertEqual(result.status, ReferenceClassStatus.PARTIAL)
        self.assertEqual(result.search_count, 1)
        self.assertEqual(len(result.candidates), 1)

    def test_all_queries_fail_yields_no_matches(self):
        provider = _FakeProvider([[], []], fail_calls={0, 1})
        result = discover_reference_class(
            _idea(), provider=provider, extractor=_stub([_relevant_candidate()])
        )
        self.assertEqual(result.status, ReferenceClassStatus.UNAVAILABLE_NO_MATCHES)
        self.assertEqual(result.search_count, 0)
        self.assertEqual(result.llm_calls, 0)
        self.assertEqual(result.evidence_store.list(), [])

    def test_extractor_exception_is_contained(self):
        provider = _FakeProvider([[_result("https://ex.com/a", "A")], []])
        result = discover_reference_class(_idea(), provider=provider, extractor=_raising_stub())
        self.assertEqual(result.status, ReferenceClassStatus.UNAVAILABLE_NO_MATCHES)
        self.assertEqual(result.llm_calls, 1)
        self.assertEqual(len(result.evidence_store.list()), 1)  # evidence retained
        self.assertEqual(result.candidates, [])

    def test_extractor_returns_nothing(self):
        provider = _FakeProvider([[_result("https://ex.com/a", "A")], []])
        result = discover_reference_class(_idea(), provider=provider, extractor=_stub([]))
        self.assertEqual(result.status, ReferenceClassStatus.UNAVAILABLE_NO_MATCHES)


# --------------------------------------------------------------------------- #
# normalisation
# --------------------------------------------------------------------------- #
class NormalizationTests(unittest.TestCase):
    def test_industry(self):
        self.assertEqual(_normalize_industry("EdTech"), "edtech")
        self.assertEqual(_normalize_industry("education technology"), "unspecified")
        self.assertEqual(_normalize_industry(None), "unspecified")
        self.assertEqual(_normalize_industry("data-ai"), "data_ai")

    def test_geography(self):
        self.assertEqual(_normalize_geography("USA"), "United States")
        self.assertEqual(_normalize_geography("united states"), "United States")
        self.assertEqual(_normalize_geography("Global"), "Global")
        self.assertIsNone(_normalize_geography("Mars"))
        self.assertIsNone(_normalize_geography(None))

    def test_enum(self):
        self.assertIs(_normalize_enum("subscription", BusinessModel, BusinessModel.UNKNOWN), BusinessModel.SUBSCRIPTION)
        self.assertIs(_normalize_enum("SaaS", ProductForm, ProductForm.UNKNOWN), ProductForm.SAAS)
        self.assertIs(_normalize_enum("nonsense", CustomerType, CustomerType.UNKNOWN), CustomerType.UNKNOWN)
        self.assertIs(_normalize_enum(None, BusinessModel, BusinessModel.UNKNOWN), BusinessModel.UNKNOWN)

    def test_off_vocabulary_attributes_become_sentinels_but_candidate_still_scores(self):
        provider = _FakeProvider([[_result("https://ex.com/a", "A", "Chegg tutoring for students")], []])
        raw = _relevant_candidate(industry="made up sector", business_model="mystery", geography="Atlantis")
        result = discover_reference_class(_idea(), provider=provider, extractor=_stub([raw]))
        self.assertEqual(len(result.candidates), 1)
        c = result.candidates[0]
        self.assertEqual(c.industry, "unspecified")
        self.assertIs(c.business_model, BusinessModel.UNKNOWN)
        self.assertIsNone(c.geography)


# --------------------------------------------------------------------------- #
# model + misc
# --------------------------------------------------------------------------- #
class ModelTests(unittest.TestCase):
    def test_discovery_result_validator_rejects_inconsistent_no_provider(self):
        from services.evidence_store import EvidenceStore

        with self.assertRaises(ValidationError):
            DiscoveryResult(
                idea_profile=_idea(),
                status=ReferenceClassStatus.UNAVAILABLE_NO_PROVIDER,
                evidence_store=EvidenceStore(),
                search_count=2,
                llm_calls=1,
                message="inconsistent",
            )

    def test_candidate_extraction_is_lenient(self):
        extraction = CandidateExtraction.model_validate(
            {"candidates": [{"name": "X", "unexpected_key": 1}], "extra_top": True}
        )
        self.assertEqual(extraction.candidates[0].name, "X")
        self.assertEqual(extraction.candidates[0].industry, "unspecified")

    def test_geo_region_labels_are_usable(self):
        self.assertIn("United States", GEO_REGION_LABELS)
        self.assertIn("Global", GEO_REGION_LABELS)
        self.assertTrue(len(GEO_REGION_LABELS) >= 5)

    def test_founding_year_out_of_range_is_dropped(self):
        provider = _FakeProvider([[_result("https://ex.com/a", "A", "Chegg tutoring for students")], []])
        raw = _relevant_candidate(founding_year=3000)
        result = discover_reference_class(_idea(), provider=provider, extractor=_stub([raw]))
        self.assertIsNone(result.candidates[0].founding_year)

    def test_full_run_is_deterministic(self):
        provider1 = _FakeProvider([[_result("https://ex.com/a", "A", "Chegg tutoring for students")], []])
        provider2 = _FakeProvider([[_result("https://ex.com/a", "A", "Chegg tutoring for students")], []])
        r1 = discover_reference_class(_idea(), provider=provider1, extractor=_stub([_relevant_candidate()]))
        r2 = discover_reference_class(_idea(), provider=provider2, extractor=_stub([_relevant_candidate()]))
        self.assertEqual(r1.status, r2.status)
        self.assertEqual(
            [(c.name, c.similarity.total, c.evidence_ids) for c in r1.candidates],
            [(c.name, c.similarity.total, c.evidence_ids) for c in r2.candidates],
        )


if __name__ == "__main__":
    unittest.main()
