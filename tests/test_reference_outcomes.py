import unittest
from datetime import date, datetime, timezone

from pydantic import HttpUrl, ValidationError

from models.evidence import Evidence, ResearchCategory, SourceQuality, SourceType
from models.reference_class import (
    OUTCOME_UNKNOWN_MAX_CONFIDENCE,
    ComparableFlag,
    ComparableStartup,
    OutcomePolarity,
    ReferenceClassStatus,
    StartupOutcome,
)
from services.evidence_store import EvidenceStore
from services.idea_profile import build_idea_profile
from services.reference_discovery import discover_reference_class
from services.reference_outcomes import (
    OutcomeVerificationResult,
    classify_outcome,
    verify_outcomes,
)
from tests.test_reference_discovery import _FakeProvider, _relevant_candidate, _result, _stub

THIS_YEAR = date.today().year
IDEA_TEXT = (
    "AI tutoring app for college students. Monthly subscription. "
    "Practice questions and personalized study plans for exam preparation."
)


def _ev(eid: str, excerpt: str, quality: SourceQuality = SourceQuality.MEDIUM, title: str = "Article"):
    return Evidence(
        evidence_id=eid,
        category=ResearchCategory.COMPETITORS,
        topic="reference class",
        title=title,
        source_url=HttpUrl(f"https://ex.com/{eid.lower()}"),
        source_name="ex.com",
        source_type=SourceType.NEWS,
        source_quality=quality,
        excerpt=excerpt,
        relevance_score=0.6,
        publication_date=None,
        retrieved_at=datetime.now(timezone.utc),
    )


# --------------------------------------------------------------------------- #
# classify_outcome -- one outcome per band
# --------------------------------------------------------------------------- #
class ClassifyOutcomeTests(unittest.TestCase):
    def test_acquired(self):
        a = classify_outcome([_ev("E-001", "Chegg was acquired by Pearson in 2019")])
        self.assertIs(a.outcome, StartupOutcome.ACQUIRED)
        self.assertIs(a.polarity, OutcomePolarity.CONTINUED)
        self.assertEqual(a.outcome_year, 2019)
        self.assertEqual(a.supporting_evidence_ids, ["E-001"])
        self.assertGreater(a.confidence, OUTCOME_UNKNOWN_MAX_CONFIDENCE)

    def test_public(self):
        a = classify_outcome([_ev("E-001", "the company went public in 2021 via a direct listing")])
        self.assertIs(a.outcome, StartupOutcome.PUBLIC)
        self.assertIs(a.polarity, OutcomePolarity.CONTINUED)

    def test_shut_down(self):
        a = classify_outcome([_ev("E-001", "the startup shut down in 2022 after running out of money")])
        self.assertIs(a.outcome, StartupOutcome.SHUT_DOWN)
        self.assertIs(a.polarity, OutcomePolarity.ENDED)

    def test_pivoted(self):
        a = classify_outcome([_ev("E-001", "the company pivoted from consumer social to enterprise saas in 2020")])
        self.assertIs(a.outcome, StartupOutcome.PIVOTED)
        self.assertIs(a.polarity, OutcomePolarity.UNCLEAR)

    def test_active_recent(self):
        a = classify_outcome([_ev("E-001", f"the startup raised a $20M series b in {THIS_YEAR}")])
        self.assertIs(a.outcome, StartupOutcome.ACTIVE)
        self.assertIs(a.polarity, OutcomePolarity.CONTINUED)

    def test_active_old_decays_to_unknown(self):
        a = classify_outcome([_ev("E-001", "the startup raised a seed round in 2013")])
        self.assertIs(a.outcome, StartupOutcome.UNKNOWN)

    def test_active_undated_decays_to_unknown(self):
        a = classify_outcome([_ev("E-001", "the startup raised a seed round from angel investors")])
        self.assertIs(a.outcome, StartupOutcome.UNKNOWN)

    def test_no_signal_is_unknown(self):
        a = classify_outcome([_ev("E-001", "Official homepage of Acme Corp. Acme builds tools. Visit acme.com", SourceQuality.HIGH)])
        self.assertIs(a.outcome, StartupOutcome.UNKNOWN)
        self.assertEqual(a.supporting_evidence_ids, [])
        self.assertLessEqual(a.confidence, OUTCOME_UNKNOWN_MAX_CONFIDENCE)

    def test_website_or_social_page_is_never_active(self):
        a = classify_outcome([_ev("E-001", "Acme Corp | LinkedIn - 50 employees - software development", SourceQuality.MEDIUM)])
        self.assertIs(a.outcome, StartupOutcome.UNKNOWN)

    def test_terminal_only_low_quality_is_unknown(self):
        a = classify_outcome([_ev("E-001", "rumor blog: acme acquired by bigco last year", SourceQuality.LOW)])
        self.assertIs(a.outcome, StartupOutcome.UNKNOWN)

    def test_empty_evidence_is_unknown(self):
        self.assertIs(classify_outcome([]).outcome, StartupOutcome.UNKNOWN)

    def test_terminal_beats_active(self):
        a = classify_outcome([_ev("E-001", "the startup shut down in 2022 after failing to raise a new round")])
        self.assertIs(a.outcome, StartupOutcome.SHUT_DOWN)

    def test_terminal_beats_pivot(self):
        a = classify_outcome([_ev("E-001", "acme pivoted in 2019 and was acquired by bigco in 2021")])
        self.assertIs(a.outcome, StartupOutcome.ACQUIRED)

    def test_pivot_beats_active(self):
        a = classify_outcome([_ev("E-001", f"acme pivoted to fintech in 2020 and raised a series a in {THIS_YEAR}")])
        self.assertIs(a.outcome, StartupOutcome.PIVOTED)

    def test_conflicting_terminal_resolved_by_year(self):
        a = classify_outcome(
            [
                _ev("E-001", "acme was acquired by bigco in 2018"),
                _ev("E-002", "acme shut down in 2021"),
            ]
        )
        self.assertIs(a.outcome, StartupOutcome.SHUT_DOWN)
        self.assertTrue(a.conflicting)
        self.assertEqual(a.outcome_year, 2021)
        self.assertEqual(a.supporting_evidence_ids, ["E-002"])

    def test_conflicting_terminal_without_years_is_unknown(self):
        a = classify_outcome(
            [
                _ev("E-001", "acme was acquired by bigco"),
                _ev("E-002", "acme has ceased operations"),
            ]
        )
        self.assertIs(a.outcome, StartupOutcome.UNKNOWN)
        self.assertTrue(a.conflicting)

    def test_two_sources_raise_confidence(self):
        one = classify_outcome([_ev("E-001", "acme was acquired by bigco in 2019")])
        two = classify_outcome(
            [
                _ev("E-001", "acme was acquired by bigco in 2019"),
                _ev("E-002", "the acquisition of acme by bigco closed in 2019"),
            ]
        )
        self.assertGreater(two.confidence, one.confidence)
        self.assertEqual(sorted(two.supporting_evidence_ids), ["E-001", "E-002"])

    def test_future_year_is_ignored(self):
        a = classify_outcome([_ev("E-001", "acme was acquired by bigco in 2099")])
        self.assertIs(a.outcome, StartupOutcome.ACQUIRED)
        self.assertIsNone(a.outcome_year)

    def test_confidence_never_exceeds_ceiling(self):
        a = classify_outcome(
            [
                _ev("E-001", "acme was acquired by bigco in 2020", SourceQuality.HIGH),
                _ev("E-002", "the acquisition of acme by bigco in 2020", SourceQuality.HIGH),
                _ev("E-003", "bigco acquired acme in 2020", SourceQuality.HIGH),
            ]
        )
        self.assertLessEqual(a.confidence, 0.95)

    def test_rationale_cites_count_and_quality_and_is_descriptive(self):
        a = classify_outcome([_ev("E-001", "acme was acquired by bigco in 2019")])
        self.assertIn("1 source(s)", a.rationale)
        self.assertIn("medium", a.rationale)
        self.assertIn("2019", a.rationale)

    def test_deterministic(self):
        evs = [_ev("E-001", "acme was acquired by bigco in 2019")]
        self.assertEqual(classify_outcome(evs).model_dump(), classify_outcome(evs).model_dump())

    def test_signals_are_recorded_for_traceability(self):
        a = classify_outcome([_ev("E-001", "acme was acquired by bigco in 2019")])
        self.assertEqual(len(a.signals), 1)
        self.assertEqual(a.signals[0].evidence_id, "E-001")
        self.assertIs(a.signals[0].outcome, StartupOutcome.ACQUIRED)


# --------------------------------------------------------------------------- #
# verify_outcomes -- over a real DiscoveryResult (fake provider + stub extractor)
# --------------------------------------------------------------------------- #
def _discovery(evidence_excerpt: str, extra_batches=None):
    # reuters.com -> classify_source() rates it NEWS / HIGH, so a signal in it is "strong".
    batches = [[_result("https://www.reuters.com/tech/x", "News", evidence_excerpt, score=0.7)], []]
    if extra_batches is not None:
        batches = extra_batches
    provider = _FakeProvider(batches)
    return discover_reference_class(
        build_idea_profile(IDEA_TEXT), provider=provider, extractor=_stub([_relevant_candidate()])
    )


class VerifyOutcomesTests(unittest.TestCase):
    def test_produces_comparable_startup_with_outcome(self):
        result = verify_outcomes(_discovery("Chegg was acquired by Pearson in 2019"))
        self.assertEqual(len(result.comparables), 1)
        comparable = result.comparables[0]
        self.assertIsInstance(comparable, ComparableStartup)
        self.assertIs(comparable.outcome.outcome, StartupOutcome.ACQUIRED)
        self.assertEqual(comparable.name, "Chegg")

    def test_passes_through_idea_and_status_and_evidence(self):
        discovery = _discovery("Chegg was acquired by Pearson in 2019")
        result = verify_outcomes(discovery)
        self.assertEqual(result.idea_profile, discovery.idea_profile)
        self.assertEqual(result.status, discovery.status)
        self.assertIs(result.evidence_store, discovery.evidence_store)

    def test_single_source_flag_is_added(self):
        result = verify_outcomes(_discovery("Chegg was acquired by Pearson in 2019"))
        self.assertIn(ComparableFlag.SINGLE_SOURCE, result.comparables[0].flags)

    def test_weak_sources_flag_when_all_low_quality(self):
        batches = [
            [_result("https://ex.com/a", "Blog", "rumor: Chegg quietly shut down in 2022")],
            [],
        ]
        # force LOW quality by using a community-looking host
        batches[0][0] = _result("https://reddit.com/r/x", "thread", "Chegg quietly shut down in 2022")
        discovery = discover_reference_class(
            build_idea_profile(IDEA_TEXT), provider=_FakeProvider(batches),
            extractor=_stub([_relevant_candidate()]),
        )
        result = verify_outcomes(discovery)
        comparable = result.comparables[0]
        self.assertIs(comparable.outcome.outcome, StartupOutcome.UNKNOWN)  # LOW-only terminal
        self.assertIn(ComparableFlag.WEAK_SOURCES, comparable.flags)

    def test_conflicting_outcome_flag_matches_assessment(self):
        batches = [
            [
                _result("https://www.reuters.com/a", "News A", "Chegg was acquired by BigCo in 2018"),
                _result("https://www.bloomberg.com/b", "News B", "Chegg shut down in 2021"),
            ],
            [],
        ]
        discovery = discover_reference_class(
            build_idea_profile(IDEA_TEXT), provider=_FakeProvider(batches),
            extractor=_stub([_relevant_candidate(supporting_evidence_ids=["E-001", "E-002"])]),
        )
        result = verify_outcomes(discovery)
        comparable = result.comparables[0]
        self.assertTrue(comparable.outcome.conflicting)
        self.assertIn(ComparableFlag.CONFLICTING_OUTCOME, comparable.flags)

    def test_pivot_flag_added(self):
        result = verify_outcomes(_discovery("Chegg pivoted from tutoring to enterprise saas in 2020"))
        comparable = result.comparables[0]
        self.assertIs(comparable.outcome.outcome, StartupOutcome.PIVOTED)
        self.assertIn(ComparableFlag.PIVOT, comparable.flags)

    def test_unknown_outcome_when_no_signal(self):
        result = verify_outcomes(_discovery("Chegg is a company. This is its homepage. Visit chegg.com"))
        self.assertIs(result.comparables[0].outcome.outcome, StartupOutcome.UNKNOWN)

    def test_no_candidates_passes_through_status_and_message(self):
        # No provider -> UNAVAILABLE_NO_PROVIDER discovery.
        discovery = discover_reference_class(build_idea_profile(IDEA_TEXT))
        result = verify_outcomes(discovery)
        self.assertEqual(result.comparables, [])
        self.assertEqual(result.status, ReferenceClassStatus.UNAVAILABLE_NO_PROVIDER)
        self.assertEqual(result.message, discovery.message)

    def test_dropped_candidates_pass_through(self):
        drop = _relevant_candidate(name="LubeCo", one_liner="industrial lubricant distributor",
                                   industry="unknown", business_model="unknown", product_form="unknown",
                                   customer_type="unknown")
        discovery = discover_reference_class(
            build_idea_profile(IDEA_TEXT),
            provider=_FakeProvider([[_result("https://ex.com/a", "N", "text")], []]),
            extractor=_stub([_relevant_candidate(), drop]),
        )
        result = verify_outcomes(discovery)
        self.assertEqual([d.name for d in result.dropped], ["LubeCo"])

    def test_outcome_evidence_is_subset_of_candidate_evidence(self):
        result = verify_outcomes(_discovery("Chegg was acquired by Pearson in 2019"))
        comparable = result.comparables[0]
        self.assertTrue(
            set(comparable.outcome.supporting_evidence_ids) <= set(comparable.evidence_ids)
        )

    def test_deterministic(self):
        d1 = _discovery("Chegg was acquired by Pearson in 2019")
        d2 = _discovery("Chegg was acquired by Pearson in 2019")
        r1, r2 = verify_outcomes(d1), verify_outcomes(d2)
        self.assertEqual(
            [(c.name, c.outcome.outcome, c.outcome.outcome_year) for c in r1.comparables],
            [(c.name, c.outcome.outcome, c.outcome.outcome_year) for c in r2.comparables],
        )


# --------------------------------------------------------------------------- #
# OutcomeVerificationResult model
# --------------------------------------------------------------------------- #
class OutcomeVerificationResultTests(unittest.TestCase):
    def test_traceability_validator_rejects_dangling_evidence(self):
        discovery = _discovery("Chegg was acquired by Pearson in 2019")
        good = verify_outcomes(discovery)
        comparable = good.comparables[0]
        with self.assertRaises(ValidationError):
            OutcomeVerificationResult(
                idea_profile=good.idea_profile,
                status=good.status,
                comparables=[comparable],
                evidence_store=EvidenceStore(),  # empty -> E-001 does not resolve
                message="x",
            )


if __name__ == "__main__":
    unittest.main()
