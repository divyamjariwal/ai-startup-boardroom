import unittest

from models.reference_class import (
    FORBIDDEN_DESCRIPTIVE_PHRASES,
    MAX_PATTERNS,
    ComparableFlag,
    PatternConfidence,
    PatternType,
    ReferenceClass,
    ReferenceClassStatus,
    StartupOutcome,
    build_summary_narrative,
)
from services.evidence_store import EvidenceStore
from services.idea_profile import build_idea_profile
from services.reference_class_engine import build_reference_class
from services.reference_discovery import discover_reference_class
from services.reference_outcomes import OutcomeVerificationResult, verify_outcomes
from tests.test_reference_discovery import _FakeProvider, _relevant_candidate, _result, _stub

IDEA_TEXT = (
    "AI tutoring app for college students. Monthly subscription. "
    "Practice questions and personalized study plans for exam preparation."
)


def _chain(batches, candidates):
    discovery = discover_reference_class(
        build_idea_profile(IDEA_TEXT),
        provider=_FakeProvider(batches),
        extractor=_stub(candidates),
    )
    return build_reference_class(verify_outcomes(discovery))


def _news(i, excerpt):
    return _result(f"https://www.reuters.com/{i}", f"News {i}", excerpt, score=0.7)


def _acquired(n, *, years=True):
    batch = [
        _news(
            i,
            f"Startup{i} was acquired by BigCo{i}" + (f" in {2019 + i}" if years else ""),
        )
        for i in range(n)
    ]
    cands = [
        _relevant_candidate(name=f"Startup{i}", supporting_evidence_ids=[f"E-{i + 1:03d}"])
        for i in range(n)
    ]
    return [batch, []], cands


# --------------------------------------------------------------------------- #
# chain / passthrough
# --------------------------------------------------------------------------- #
class ChainTests(unittest.TestCase):
    def test_happy_path_shape(self):
        batches, cands = _acquired(3)
        rc = _chain(batches, cands)
        self.assertIsInstance(rc, ReferenceClass)
        self.assertIs(rc.status, ReferenceClassStatus.AVAILABLE)
        self.assertEqual(len(rc.comparables), 3)
        self.assertEqual(rc.discovery_search_count, 2)
        self.assertEqual(rc.verification_search_count, 0)
        self.assertEqual(rc.llm_calls, 1)

    def test_idea_profile_and_store_passthrough(self):
        batches, cands = _acquired(2)
        discovery = discover_reference_class(
            build_idea_profile(IDEA_TEXT), provider=_FakeProvider(batches), extractor=_stub(cands)
        )
        rc = build_reference_class(verify_outcomes(discovery))
        self.assertEqual(rc.idea_profile, discovery.idea_profile)
        self.assertIs(rc.evidence_store, discovery.evidence_store)

    def test_dropped_candidates_pass_through(self):
        batch = [_news(0, "Startup0 was acquired by BigCo in 2019"), _news(1, "info")]
        drop = _relevant_candidate(
            name="LubeCo", one_liner="industrial lubricant distributor", industry="unknown",
            business_model="unknown", product_form="unknown", customer_type="unknown",
            supporting_evidence_ids=["E-002"],
        )
        rc = _chain(
            [batch, []],
            [_relevant_candidate(name="Startup0", supporting_evidence_ids=["E-001"]), drop],
        )
        self.assertEqual([d.name for d in rc.dropped_candidates], ["LubeCo"])
        self.assertEqual(rc.summary.dropped_count, 1)


# --------------------------------------------------------------------------- #
# summary
# --------------------------------------------------------------------------- #
class SummaryTests(unittest.TestCase):
    def test_by_outcome_and_polarity_counts(self):
        batch = [
            _news(0, "Startup0 was acquired by BigCo in 2019"),
            _news(1, "Startup1 shut down in 2021"),
            _news(2, "Startup2 has a homepage and an address"),
        ]
        cands = [
            _relevant_candidate(name=f"Startup{i}", supporting_evidence_ids=[f"E-{i + 1:03d}"])
            for i in range(3)
        ]
        rc = _chain([batch, []], cands)
        self.assertEqual(
            rc.summary.by_outcome,
            {StartupOutcome.ACQUIRED: 1, StartupOutcome.SHUT_DOWN: 1, StartupOutcome.UNKNOWN: 1},
        )
        self.assertEqual(rc.summary.continued_count, 1)
        self.assertEqual(rc.summary.ended_count, 1)
        self.assertEqual(rc.summary.unclear_count, 1)
        self.assertEqual(rc.summary.total_comparables, 3)

    def test_narrative_matches_builder(self):
        batches, cands = _acquired(3)
        rc = _chain(batches, cands)
        self.assertEqual(
            rc.summary.narrative,
            build_summary_narrative(
                total_comparables=3, continued_count=3, ended_count=0, unclear_count=0,
                dropped_count=0,
            ),
        )
        self.assertNotIn("were excluded", rc.summary.narrative)

    def test_narrative_mentions_dropped(self):
        batch = [_news(0, "Startup0 was acquired by BigCo in 2019"), _news(1, "info")]
        drop = _relevant_candidate(
            name="LubeCo", one_liner="industrial lubricant distributor", industry="unknown",
            business_model="unknown", product_form="unknown", customer_type="unknown",
            supporting_evidence_ids=["E-002"],
        )
        rc = _chain(
            [batch, []],
            [_relevant_candidate(name="Startup0", supporting_evidence_ids=["E-001"]), drop],
        )
        self.assertIn("were excluded", rc.summary.narrative)


# --------------------------------------------------------------------------- #
# ordering
# --------------------------------------------------------------------------- #
class OrderingTests(unittest.TestCase):
    def test_tie_break_is_alphabetical_by_name(self):
        batch = [_news(i, f"co{i} was acquired by bigco in 2019") for i in range(3)]
        cands = [
            _relevant_candidate(name=name, supporting_evidence_ids=[f"E-{i + 1:03d}"])
            for i, name in enumerate(["Zeta", "Alpha", "Mid"])
        ]
        rc = _chain([batch, []], cands)
        self.assertEqual([c.name for c in rc.comparables], ["Alpha", "Mid", "Zeta"])

    def test_higher_similarity_sorts_first(self):
        batch = [_news(0, "A was acquired by bigco in 2019"), _news(1, "B was acquired by bigco in 2019")]
        cands = [
            _relevant_candidate(name="MatchIndustry", industry="edtech", supporting_evidence_ids=["E-001"]),
            _relevant_candidate(name="OffIndustry", industry="fintech", supporting_evidence_ids=["E-002"]),
        ]
        rc = _chain([batch, []], cands)
        self.assertEqual([c.name for c in rc.comparables], ["MatchIndustry", "OffIndustry"])
        self.assertGreater(rc.comparables[0].similarity.total, rc.comparables[1].similarity.total)


# --------------------------------------------------------------------------- #
# patterns
# --------------------------------------------------------------------------- #
class PatternTests(unittest.TestCase):
    def _pattern(self, rc, pattern_type):
        return [p for p in rc.patterns if p.pattern_type is pattern_type]

    def test_outcome_tendency_majority_is_medium(self):
        batches, cands = _acquired(3)
        rc = _chain(batches, cands)
        tendencies = self._pattern(rc, PatternType.OUTCOME_TENDENCY)
        self.assertEqual(len(tendencies), 1)
        self.assertEqual(tendencies[0].support_count, 3)
        self.assertIs(tendencies[0].confidence, PatternConfidence.MEDIUM)
        self.assertIn("were acquired by another company", tendencies[0].text)

    def test_outcome_tendency_minority_is_low(self):
        batch = [
            _news(0, "Startup0 was acquired by BigCo in 2019"),
            _news(1, "Startup1 was acquired by BigCo in 2020"),
            _news(2, "Startup2 homepage"),
            _news(3, "Startup3 homepage"),
        ]
        cands = [
            _relevant_candidate(name=f"Startup{i}", supporting_evidence_ids=[f"E-{i + 1:03d}"])
            for i in range(4)
        ]
        rc = _chain([batch, []], cands)
        tendencies = self._pattern(rc, PatternType.OUTCOME_TENDENCY)
        self.assertEqual(tendencies[0].support_count, 2)
        self.assertIs(tendencies[0].confidence, PatternConfidence.LOW)

    def test_shutdown_is_recurring_risk_not_tendency(self):
        batch = [_news(i, f"Startup{i} shut down in 2021") for i in range(2)]
        cands = [
            _relevant_candidate(name=f"Startup{i}", supporting_evidence_ids=[f"E-{i + 1:03d}"])
            for i in range(2)
        ]
        rc = _chain([batch, []], cands)
        self.assertEqual(self._pattern(rc, PatternType.OUTCOME_TENDENCY), [])
        risks = self._pattern(rc, PatternType.RECURRING_RISK)
        self.assertEqual(len(risks), 1)
        self.assertIn("shut down", risks[0].text)

    def test_pivot_is_common_pivot_and_flags_present(self):
        batch = [_news(i, f"Startup{i} pivoted from tutoring to fintech in 2020") for i in range(2)]
        cands = [
            _relevant_candidate(name=f"Startup{i}", supporting_evidence_ids=[f"E-{i + 1:03d}"])
            for i in range(2)
        ]
        rc = _chain([batch, []], cands)
        pivots = self._pattern(rc, PatternType.COMMON_PIVOT)
        self.assertEqual(len(pivots), 1)
        self.assertEqual(pivots[0].support_count, 2)
        for comparable in rc.comparables:
            self.assertIn(ComparableFlag.PIVOT, comparable.flags)

    def test_gtm_pattern_for_shared_business_model(self):
        batches, cands = _acquired(3)
        rc = _chain(batches, cands)
        gtm = self._pattern(rc, PatternType.GTM_PATTERN)
        hints = {p.linked_assumption_hint for p in gtm}
        self.assertIn("business_model", hints)
        bm_pattern = next(p for p in gtm if p.linked_assumption_hint == "business_model")
        self.assertIn("subscription business model", bm_pattern.text)

    def test_gtm_pattern_skipped_for_minority_value(self):
        batch = [_news(i, f"co{i} homepage") for i in range(4)]
        models = ["subscription", "advertising", "freemium", "licensing"]
        cands = [
            _relevant_candidate(
                name=f"Startup{i}", business_model=models[i], supporting_evidence_ids=[f"E-{i + 1:03d}"]
            )
            for i in range(4)
        ]
        rc = _chain([batch, []], cands)
        self.assertNotIn(
            "business_model", {p.linked_assumption_hint for p in rc.patterns}
        )

    def test_all_unknown_outcomes_yield_no_outcome_pattern(self):
        batch = [_news(i, f"Startup{i} is a company with a homepage") for i in range(3)]
        cands = [
            _relevant_candidate(name=f"Startup{i}", supporting_evidence_ids=[f"E-{i + 1:03d}"])
            for i in range(3)
        ]
        rc = _chain([batch, []], cands)
        self.assertEqual(self._pattern(rc, PatternType.OUTCOME_TENDENCY), [])
        self.assertEqual(self._pattern(rc, PatternType.RECURRING_RISK), [])
        self.assertEqual(self._pattern(rc, PatternType.COMMON_PIVOT), [])

    def test_pattern_ids_are_sequential_and_unique(self):
        batches, cands = _acquired(3)
        rc = _chain(batches, cands)
        ids = [p.id for p in rc.patterns]
        self.assertEqual(ids, [f"RCP-{i:02d}" for i in range(1, len(ids) + 1)])
        self.assertEqual(len(set(ids)), len(ids))

    def test_pattern_invariants(self):
        batches, cands = _acquired(3)
        rc = _chain(batches, cands)
        names = {c.name for c in rc.comparables}
        for p in rc.patterns:
            self.assertEqual(p.support_count, len(p.supporting_startups))
            self.assertTrue(set(p.supporting_startups) <= names)
            lowered = p.text.lower()
            for phrase in FORBIDDEN_DESCRIPTIVE_PHRASES:
                self.assertNotIn(phrase, lowered)
        self.assertLessEqual(len(rc.patterns), MAX_PATTERNS)

    def test_no_patterns_with_single_comparable(self):
        rc = _chain(
            [[_news(0, "Startup0 was acquired by BigCo in 2019")], []],
            [_relevant_candidate(name="Startup0", supporting_evidence_ids=["E-001"])],
        )
        self.assertEqual(rc.patterns, [])

    def test_year_span_in_text(self):
        batches, cands = _acquired(2, years=True)
        rc = _chain(batches, cands)
        tendency = next(p for p in rc.patterns if p.pattern_type is PatternType.OUTCOME_TENDENCY)
        self.assertIn("(2019-2020)", tendency.text)

    def test_no_year_span_when_years_absent(self):
        batches, cands = _acquired(2, years=False)
        rc = _chain(batches, cands)
        tendency = next(p for p in rc.patterns if p.pattern_type is PatternType.OUTCOME_TENDENCY)
        self.assertNotIn("(", tendency.text)


# --------------------------------------------------------------------------- #
# status
# --------------------------------------------------------------------------- #
class StatusTests(unittest.TestCase):
    def test_no_provider(self):
        discovery = discover_reference_class(build_idea_profile(IDEA_TEXT))
        rc = build_reference_class(verify_outcomes(discovery))
        self.assertIs(rc.status, ReferenceClassStatus.UNAVAILABLE_NO_PROVIDER)
        self.assertEqual(rc.comparables, [])
        self.assertEqual(rc.patterns, [])
        self.assertEqual(rc.discovery_search_count, 0)
        self.assertEqual(rc.llm_calls, 0)

    def test_no_matches(self):
        discovery = discover_reference_class(
            build_idea_profile(IDEA_TEXT),
            provider=_FakeProvider([[_news(0, "info")], []]),
            extractor=_stub([]),
        )
        rc = build_reference_class(verify_outcomes(discovery))
        self.assertIs(rc.status, ReferenceClassStatus.UNAVAILABLE_NO_MATCHES)
        self.assertEqual(rc.comparables, [])

    def test_partial(self):
        batches, cands = _acquired(2)
        # call 0 fails; the evidence is served by the surviving call 1.
        discovery = discover_reference_class(
            build_idea_profile(IDEA_TEXT),
            provider=_FakeProvider([[], batches[0]], fail_calls={0}),
            extractor=_stub(cands),
        )
        rc = build_reference_class(verify_outcomes(discovery))
        self.assertIs(rc.status, ReferenceClassStatus.PARTIAL)
        self.assertEqual(len(rc.comparables), 2)


# --------------------------------------------------------------------------- #
# direct verification-result input + determinism
# --------------------------------------------------------------------------- #
class DirectAndDeterminismTests(unittest.TestCase):
    def test_empty_verification_result(self):
        verification = OutcomeVerificationResult(
            idea_profile=build_idea_profile(IDEA_TEXT),
            status=ReferenceClassStatus.AVAILABLE,
            comparables=[],
            evidence_store=EvidenceStore(),
            message="none",
        )
        rc = build_reference_class(verification)
        self.assertEqual(rc.comparables, [])
        self.assertEqual(rc.patterns, [])
        self.assertEqual(rc.summary.total_comparables, 0)
        self.assertIn("Among the 0 verified comparable startups", rc.summary.narrative)

    def test_verification_result_carries_discovery_counts(self):
        batches, cands = _acquired(2)
        discovery = discover_reference_class(
            build_idea_profile(IDEA_TEXT), provider=_FakeProvider(batches), extractor=_stub(cands)
        )
        verification = verify_outcomes(discovery)
        self.assertEqual(verification.search_count, discovery.search_count)
        self.assertEqual(verification.llm_calls, discovery.llm_calls)

    def test_deterministic(self):
        batches, cands = _acquired(3)
        rc1 = _chain(batches, cands)
        batches2, cands2 = _acquired(3)
        rc2 = _chain(batches2, cands2)
        self.assertEqual(
            [(c.name, c.outcome.outcome, c.similarity.total) for c in rc1.comparables],
            [(c.name, c.outcome.outcome, c.similarity.total) for c in rc2.comparables],
        )
        self.assertEqual(
            [(p.id, p.pattern_type, tuple(p.supporting_startups), p.confidence, p.text) for p in rc1.patterns],
            [(p.id, p.pattern_type, tuple(p.supporting_startups), p.confidence, p.text) for p in rc2.patterns],
        )
        self.assertEqual(rc1.summary.model_dump(), rc2.summary.model_dump())


if __name__ == "__main__":
    unittest.main()
