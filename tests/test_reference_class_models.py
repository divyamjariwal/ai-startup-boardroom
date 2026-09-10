import math
import unittest
from datetime import datetime, timezone

from pydantic import ValidationError

from models.evidence import Evidence, ResearchCategory, SourceQuality, SourceType
from models.reference_class import (
    MAX_COMPARABLES,
    MAX_DISCOVERY_QUERIES,
    MAX_VERIFICATION_SEARCHES,
    PATTERN_MEDIUM_CONFIDENCE_MIN_SUPPORT,
    PATTERN_MIN_SUPPORT,
    POLARITY_BY_OUTCOME,
    SIMILARITY_DIVERGENT_THRESHOLD,
    SIMILARITY_INCLUSION_THRESHOLD,
    SIMILARITY_MATCH_THRESHOLD,
    SIMILARITY_WEIGHTS,
    UNRESOLVED_FIELD_ORDER,
    BusinessModel,
    ComparableFlag,
    ComparableStartup,
    CustomerType,
    DimensionScore,
    DropReason,
    DroppedCandidate,
    IdeaProfile,
    OutcomeAssessment,
    OutcomePolarity,
    OutcomeSignal,
    PatternConfidence,
    PatternType,
    ProductForm,
    RawCandidate,
    ReferenceClass,
    ReferenceClassPattern,
    ReferenceClassStatus,
    ReferenceClassSummary,
    SimilarityBreakdown,
    SimilarityDimension,
    StartupOutcome,
    UnresolvedField,
    VerifiedCandidate,
    build_summary_narrative,
)
from services.evidence_store import EvidenceStore


# --------------------------------------------------------------------------- #
# Factories
# --------------------------------------------------------------------------- #
def _profile(**kw) -> IdeaProfile:
    base = dict(
        raw_text="a subscription tutoring app for college students in the united states",
        customer_type=CustomerType.CONSUMER,
        customer_descriptor="college students",
        problem="students cannot find affordable exam preparation",
        product_form=ProductForm.APP,
        business_model=BusinessModel.SUBSCRIPTION,
        industry="edtech",
        geography="United States",
        keywords=["tutoring", "exam prep"],
        unresolved_fields=[],
    )
    base.update(kw)
    return IdeaProfile(**base)


def _dims(value: float = 0.5) -> list[DimensionScore]:
    return [
        DimensionScore(
            dimension=dim,
            score=value,
            weight=SIMILARITY_WEIGHTS[dim],
            weighted_score=value * SIMILARITY_WEIGHTS[dim],
            basis=f"{dim.value}: constructed for tests",
        )
        for dim in SimilarityDimension
    ]


def _breakdown(
    value: float = 0.5,
    rationale: str = "similar customer and problem; different geography",
) -> SimilarityBreakdown:
    dims = _dims(value)
    total = round(100 * sum(d.weighted_score for d in dims))
    return SimilarityBreakdown(
        dimensions=dims,
        total=total,
        matched_dimensions=[
            d.dimension for d in dims if d.score >= SIMILARITY_MATCH_THRESHOLD
        ],
        divergent_dimensions=[
            d.dimension for d in dims if d.score <= SIMILARITY_DIVERGENT_THRESHOLD
        ],
        rationale=rationale,
    )


def _outcome(
    outcome: StartupOutcome = StartupOutcome.ACQUIRED,
    evidence_id: str = "E-001",
    year: int = 2019,
    confidence: float = 0.7,
    conflicting: bool = False,
    rationale: str = "Two established-news sources report an acquisition in 2019.",
) -> OutcomeAssessment:
    polarity = POLARITY_BY_OUTCOME[outcome]
    signal = OutcomeSignal(
        outcome=outcome,
        phrase="acquired by",
        evidence_id=evidence_id,
        source_quality=SourceQuality.MEDIUM,
        detected_year=year,
    )
    return OutcomeAssessment(
        outcome=outcome,
        polarity=polarity,
        outcome_year=year,
        confidence=confidence,
        supporting_evidence_ids=[evidence_id],
        signals=[signal],
        rationale=rationale,
        conflicting=conflicting,
    )


def _unknown_outcome(confidence: float = 0.1) -> OutcomeAssessment:
    return OutcomeAssessment(
        outcome=StartupOutcome.UNKNOWN,
        polarity=OutcomePolarity.UNCLEAR,
        confidence=confidence,
        rationale="No reliable outcome signal in retrieved sources.",
    )


def _verified_candidate(name: str = "Startup A", value: float = 0.5, **kw) -> VerifiedCandidate:
    breakdown = _breakdown(value)
    base = dict(
        name=name,
        one_liner=f"{name} offered on-demand study help",
        industry="edtech",
        similarity=breakdown,
        evidence_ids=["E-001"],
        is_company_verified=True,
        is_relevant=breakdown.total >= SIMILARITY_INCLUSION_THRESHOLD,
    )
    base.update(kw)
    return VerifiedCandidate(**base)


def _comparable(
    name: str = "Startup A",
    value: float = 0.5,
    evidence_ids: list[str] | None = None,
    outcome: OutcomeAssessment | None = None,
    flags: list[ComparableFlag] | None = None,
    **kw,
) -> ComparableStartup:
    evidence_ids = evidence_ids or ["E-001"]
    breakdown = _breakdown(value)
    base = dict(
        name=name,
        one_liner=f"{name} offered on-demand study help",
        industry="edtech",
        similarity=breakdown,
        evidence_ids=evidence_ids,
        is_company_verified=True,
        is_relevant=breakdown.total >= SIMILARITY_INCLUSION_THRESHOLD,
        outcome=outcome or _outcome(evidence_id=evidence_ids[0]),
        flags=flags or [],
    )
    base.update(kw)
    return ComparableStartup(**base)


def _evidence(eid: str = "E-001", url: str = "https://example.com/a") -> Evidence:
    return Evidence(
        evidence_id=eid,
        category=ResearchCategory.COMPETITORS,
        topic="reference class",
        title="Article",
        source_url=url,
        source_name="example.com",
        source_type=SourceType.NEWS,
        source_quality=SourceQuality.MEDIUM,
        excerpt="constructed for tests",
        relevance_score=0.5,
        retrieved_at=datetime.now(timezone.utc),
    )


def _store(*evidence: Evidence) -> EvidenceStore:
    store = EvidenceStore()
    for item in evidence:
        store.add(item)
    return store


def _summary(by_outcome: dict[StartupOutcome, int], dropped: int = 0) -> ReferenceClassSummary:
    continued = sum(
        v for k, v in by_outcome.items() if POLARITY_BY_OUTCOME[k] is OutcomePolarity.CONTINUED
    )
    ended = sum(
        v for k, v in by_outcome.items() if POLARITY_BY_OUTCOME[k] is OutcomePolarity.ENDED
    )
    unclear = sum(
        v for k, v in by_outcome.items() if POLARITY_BY_OUTCOME[k] is OutcomePolarity.UNCLEAR
    )
    total = sum(by_outcome.values())
    return ReferenceClassSummary(
        total_comparables=total,
        by_outcome=by_outcome,
        continued_count=continued,
        ended_count=ended,
        unclear_count=unclear,
        dropped_count=dropped,
        narrative=build_summary_narrative(
            total_comparables=total,
            continued_count=continued,
            ended_count=ended,
            unclear_count=unclear,
            dropped_count=dropped,
        ),
    )


def _reference_class(
    comparables: list[ComparableStartup] | None = None,
    dropped: list[DroppedCandidate] | None = None,
    patterns: list[ReferenceClassPattern] | None = None,
    store: EvidenceStore | None = None,
    status: ReferenceClassStatus = ReferenceClassStatus.AVAILABLE,
    discovery: int = 3,
    verification: int = 4,
    **kw,
) -> ReferenceClass:
    comparables = [] if comparables is None else comparables
    dropped = dropped or []
    patterns = patterns or []
    if store is None:
        store = _store(
            _evidence("E-001", "https://a.example/1"),
            _evidence("E-002", "https://b.example/2"),
        )
    by_outcome: dict[StartupOutcome, int] = {}
    for c in comparables:
        by_outcome[c.outcome.outcome] = by_outcome.get(c.outcome.outcome, 0) + 1
    base = dict(
        idea_profile=_profile(),
        status=status,
        comparables=comparables,
        dropped_candidates=dropped,
        patterns=patterns,
        summary=_summary(by_outcome, dropped=len(dropped)),
        discovery_search_count=discovery,
        verification_search_count=verification,
        evidence_store=store,
    )
    base.update(kw)
    return ReferenceClass(**base)


# --------------------------------------------------------------------------- #
# IdeaProfile
# --------------------------------------------------------------------------- #
class IdeaProfileTests(unittest.TestCase):
    def test_fully_resolved_profile_is_valid(self):
        profile = _profile()
        self.assertEqual(profile.industry, "edtech")
        self.assertEqual(profile.unresolved_fields, [])

    def test_sentinel_without_unresolved_marker_is_rejected(self):
        with self.assertRaises(ValidationError):
            _profile(industry="unspecified")

    def test_sentinel_with_matching_unresolved_marker_is_valid(self):
        profile = _profile(
            industry="unspecified", unresolved_fields=[UnresolvedField.INDUSTRY]
        )
        self.assertIn(UnresolvedField.INDUSTRY, profile.unresolved_fields)

    def test_unresolved_marker_without_sentinel_is_rejected(self):
        with self.assertRaises(ValidationError):
            _profile(unresolved_fields=[UnresolvedField.INDUSTRY])

    def test_unresolved_fields_must_be_canonically_ordered(self):
        with self.assertRaises(ValidationError):
            _profile(
                problem="unspecified",
                geography="unspecified",
                unresolved_fields=[UnresolvedField.GEOGRAPHY, UnresolvedField.PROBLEM],
            )

    def test_unresolved_fields_reject_duplicates(self):
        with self.assertRaises(ValidationError):
            _profile(
                problem="unspecified",
                unresolved_fields=[UnresolvedField.PROBLEM, UnresolvedField.PROBLEM],
            )

    def test_keywords_reject_duplicates(self):
        with self.assertRaises(ValidationError):
            _profile(keywords=["tutoring", "tutoring"])

    def test_keywords_reject_uppercase(self):
        with self.assertRaises(ValidationError):
            _profile(keywords=["Tutoring"])

    def test_keywords_allow_single_bigram_but_reject_trigram(self):
        self.assertEqual(_profile(keywords=["exam prep"]).keywords, ["exam prep"])
        with self.assertRaises(ValidationError):
            _profile(keywords=["exam prep now"])

    def test_raw_text_must_be_non_empty(self):
        with self.assertRaises(ValidationError):
            _profile(raw_text="")

    def test_extra_fields_are_forbidden(self):
        with self.assertRaises(ValidationError):
            _profile(confidence=0.9)

    def test_all_sentinels_with_full_canonical_unresolved_list_is_valid(self):
        profile = _profile(
            customer_type=CustomerType.UNKNOWN,
            customer_descriptor="unspecified",
            problem="unspecified",
            product_form=ProductForm.UNKNOWN,
            business_model=BusinessModel.UNKNOWN,
            industry="unspecified",
            geography="unspecified",
            unresolved_fields=list(UNRESOLVED_FIELD_ORDER),
        )
        self.assertEqual(profile.unresolved_fields, list(UNRESOLVED_FIELD_ORDER))


# --------------------------------------------------------------------------- #
# Similarity
# --------------------------------------------------------------------------- #
class SimilarityTests(unittest.TestCase):
    def test_valid_breakdown_round_trips(self):
        breakdown = _breakdown(0.7)
        self.assertEqual(breakdown.total, 70)
        self.assertEqual(len(breakdown.matched_dimensions), 6)

    def test_weighted_score_must_equal_score_times_weight(self):
        with self.assertRaises(ValidationError):
            DimensionScore(
                dimension=SimilarityDimension.PROBLEM,
                score=0.5,
                weight=SIMILARITY_WEIGHTS[SimilarityDimension.PROBLEM],
                weighted_score=0.9,
                basis="x",
            )

    def test_weight_must_match_approved_constant(self):
        tampered = DimensionScore(
            dimension=SimilarityDimension.PROBLEM, score=0.5, weight=0.9,
            weighted_score=0.5 * 0.9, basis="x",
        )
        rest = [d for d in _dims(0.5) if d.dimension is not SimilarityDimension.PROBLEM]
        with self.assertRaises(ValidationError):
            SimilarityBreakdown(
                dimensions=[tampered, *rest], total=50, matched_dimensions=[],
                divergent_dimensions=[], rationale="x",
            )

    def test_wrong_total_is_rejected(self):
        dims = _dims(0.5)
        with self.assertRaises(ValidationError):
            SimilarityBreakdown(
                dimensions=dims, total=99, matched_dimensions=[], divergent_dimensions=[],
                rationale="x",
            )

    def test_missing_a_dimension_is_rejected(self):
        with self.assertRaises(ValidationError):
            SimilarityBreakdown(
                dimensions=_dims(0.5)[:5], total=40, matched_dimensions=[],
                divergent_dimensions=[], rationale="x",
            )

    def test_matched_dimensions_must_reflect_threshold(self):
        dims = _dims(0.7)
        with self.assertRaises(ValidationError):
            SimilarityBreakdown(
                dimensions=dims, total=70, matched_dimensions=[], divergent_dimensions=[],
                rationale="x",
            )

    def test_rationale_rejects_predictive_language(self):
        with self.assertRaises(ValidationError):
            _breakdown(0.5, rationale="high success rate expected for this cohort")


# --------------------------------------------------------------------------- #
# Outcome verification
# --------------------------------------------------------------------------- #
class OutcomeTests(unittest.TestCase):
    def test_valid_concrete_assessment(self):
        assessment = _outcome(StartupOutcome.ACQUIRED)
        self.assertEqual(assessment.polarity, OutcomePolarity.CONTINUED)

    def test_polarity_must_match_outcome(self):
        with self.assertRaises(ValidationError):
            OutcomeAssessment(
                outcome=StartupOutcome.SHUT_DOWN,
                polarity=OutcomePolarity.CONTINUED,
                confidence=0.5,
                supporting_evidence_ids=["E-001"],
                signals=[
                    OutcomeSignal(
                        outcome=StartupOutcome.SHUT_DOWN, phrase="ceased operations",
                        evidence_id="E-001", source_quality=SourceQuality.MEDIUM,
                    )
                ],
                rationale="x",
            )

    def test_polarity_mapping_covers_pivoted_and_shut_down(self):
        self.assertEqual(POLARITY_BY_OUTCOME[StartupOutcome.PIVOTED], OutcomePolarity.UNCLEAR)
        self.assertEqual(POLARITY_BY_OUTCOME[StartupOutcome.SHUT_DOWN], OutcomePolarity.ENDED)

    def test_unknown_outcome_caps_confidence(self):
        with self.assertRaises(ValidationError):
            _unknown_outcome(confidence=0.5)

    def test_unknown_outcome_cannot_cite_evidence_or_year(self):
        with self.assertRaises(ValidationError):
            OutcomeAssessment(
                outcome=StartupOutcome.UNKNOWN, polarity=OutcomePolarity.UNCLEAR,
                confidence=0.1, supporting_evidence_ids=["E-001"], rationale="x",
            )

    def test_concrete_outcome_requires_supporting_evidence(self):
        with self.assertRaises(ValidationError):
            OutcomeAssessment(
                outcome=StartupOutcome.ACQUIRED, polarity=OutcomePolarity.CONTINUED,
                confidence=0.6, rationale="x",
            )

    def test_supporting_evidence_must_appear_in_signals(self):
        with self.assertRaises(ValidationError):
            OutcomeAssessment(
                outcome=StartupOutcome.ACQUIRED, polarity=OutcomePolarity.CONTINUED,
                confidence=0.6, supporting_evidence_ids=["E-002"],
                signals=[
                    OutcomeSignal(
                        outcome=StartupOutcome.ACQUIRED, phrase="acquired by",
                        evidence_id="E-001", source_quality=SourceQuality.MEDIUM,
                    )
                ],
                rationale="x",
            )

    def test_supporting_signal_must_match_outcome(self):
        with self.assertRaises(ValidationError):
            OutcomeAssessment(
                outcome=StartupOutcome.ACQUIRED, polarity=OutcomePolarity.CONTINUED,
                confidence=0.6, supporting_evidence_ids=["E-001"],
                signals=[
                    OutcomeSignal(
                        outcome=StartupOutcome.SHUT_DOWN, phrase="ceased operations",
                        evidence_id="E-001", source_quality=SourceQuality.MEDIUM,
                    )
                ],
                rationale="x",
            )

    def test_signal_cannot_be_unknown(self):
        with self.assertRaises(ValidationError):
            OutcomeSignal(
                outcome=StartupOutcome.UNKNOWN, phrase="unclear", evidence_id="E-001",
                source_quality=SourceQuality.LOW,
            )

    def test_signal_rejects_future_year(self):
        with self.assertRaises(ValidationError):
            OutcomeSignal(
                outcome=StartupOutcome.ACQUIRED, phrase="acquired by", evidence_id="E-001",
                source_quality=SourceQuality.MEDIUM, detected_year=2400,
            )

    def test_outcome_rationale_rejects_predictive_language(self):
        with self.assertRaises(ValidationError):
            _outcome(rationale="this company will succeed based on its trajectory")


# --------------------------------------------------------------------------- #
# Candidate pipeline
# --------------------------------------------------------------------------- #
class RawCandidateTests(unittest.TestCase):
    def test_valid(self):
        raw = RawCandidate(
            name="Chegg Tutors", normalized_name="chegg tutors",
            discovery_evidence_ids=["E-001"], mention_count=2,
        )
        self.assertEqual(raw.mention_count, 2)

    def test_requires_discovery_evidence(self):
        with self.assertRaises(ValidationError):
            RawCandidate(
                name="X", normalized_name="x", discovery_evidence_ids=[], mention_count=1,
            )

    def test_normalized_name_must_be_lowercased_and_collapsed(self):
        with self.assertRaises(ValidationError):
            RawCandidate(
                name="X", normalized_name="Chegg  Tutors",
                discovery_evidence_ids=["E-001"], mention_count=1,
            )


class VerifiedCandidateTests(unittest.TestCase):
    def test_valid(self):
        candidate = _verified_candidate()
        self.assertTrue(candidate.is_relevant)

    def test_requires_evidence(self):
        with self.assertRaises(ValidationError):
            _verified_candidate(evidence_ids=[])

    def test_is_relevant_must_match_similarity_total(self):
        with self.assertRaises(ValidationError):
            _verified_candidate(value=0.3, is_relevant=True)

    def test_low_similarity_candidate_is_not_relevant(self):
        candidate = _verified_candidate(value=0.3, is_relevant=False)
        self.assertLess(candidate.similarity.total, SIMILARITY_INCLUSION_THRESHOLD)

    def test_rejects_future_founding_year(self):
        with self.assertRaises(ValidationError):
            _verified_candidate(founding_year=2400)

    def test_source_urls_field_is_removed(self):
        with self.assertRaises(ValidationError):
            _verified_candidate(source_urls=["https://x.example"])


class ComparableStartupTests(unittest.TestCase):
    def test_valid(self):
        comparable = _comparable()
        self.assertEqual(comparable.outcome.outcome, StartupOutcome.ACQUIRED)

    def test_must_be_company_verified(self):
        with self.assertRaises(ValidationError):
            _comparable(is_company_verified=False)

    def test_must_be_relevant(self):
        with self.assertRaises(ValidationError):
            _comparable(value=0.3, is_relevant=False)

    def test_outcome_evidence_must_be_subset_of_candidate_evidence(self):
        with self.assertRaises(ValidationError):
            _comparable(evidence_ids=["E-002"], outcome=_outcome(evidence_id="E-001"))

    def test_conflicting_flag_must_agree_with_outcome(self):
        with self.assertRaises(ValidationError):
            _comparable(flags=[ComparableFlag.CONFLICTING_OUTCOME])

    def test_pivot_flag_requires_pivot_outcome_or_rationale(self):
        with self.assertRaises(ValidationError):
            _comparable(flags=[ComparableFlag.PIVOT])
        ok = _comparable(
            flags=[ComparableFlag.PIVOT],
            outcome=_outcome(
                StartupOutcome.PIVOTED,
                rationale="Company pivoted from consumer tutoring to B2B in 2020.",
            ),
        )
        self.assertIn(ComparableFlag.PIVOT, ok.flags)

    def test_source_urls_field_is_removed(self):
        with self.assertRaises(ValidationError):
            _comparable(source_urls=["https://x.example"])


class DroppedCandidateTests(unittest.TestCase):
    def test_valid_non_duplicate(self):
        dropped = DroppedCandidate(
            name="Ghost Co", reason=DropReason.NOT_VERIFIED_AS_COMPANY,
            detail="No retrieved source confirms this is a real company.",
        )
        self.assertIsNone(dropped.merged_into)

    def test_duplicate_requires_merged_into(self):
        with self.assertRaises(ValidationError):
            DroppedCandidate(name="X", reason=DropReason.DUPLICATE, detail="dupe")

    def test_non_duplicate_rejects_merged_into(self):
        with self.assertRaises(ValidationError):
            DroppedCandidate(
                name="X", reason=DropReason.INSUFFICIENT_RELEVANCE, detail="off topic",
                merged_into="Y",
            )

    def test_source_urls_field_is_removed(self):
        with self.assertRaises(ValidationError):
            DroppedCandidate(
                name="X", reason=DropReason.NO_EVIDENCE_RETRIEVED, detail="nothing",
                source_urls=["https://x.example"],
            )


# --------------------------------------------------------------------------- #
# Aggregation
# --------------------------------------------------------------------------- #
class PatternTests(unittest.TestCase):
    def test_low_confidence_two_supporters_is_valid(self):
        pattern = ReferenceClassPattern(
            id="RCP-01", text="2 of the 6 retrieved comparables pivoted away from B2C.",
            pattern_type=PatternType.COMMON_PIVOT,
            supporting_startups=["Startup A", "Startup B"], support_count=2,
            confidence=PatternConfidence.LOW,
        )
        self.assertEqual(pattern.support_count, 2)

    def test_medium_confidence_requires_three_supporters(self):
        with self.assertRaises(ValidationError):
            ReferenceClassPattern(
                id="RCP-01", text="observed in the retrieved sample",
                pattern_type=PatternType.OUTCOME_TENDENCY,
                supporting_startups=["A", "B"], support_count=2,
                confidence=PatternConfidence.MEDIUM,
            )

    def test_support_count_must_match_supporters(self):
        with self.assertRaises(ValidationError):
            ReferenceClassPattern(
                id="RCP-01", text="x", pattern_type=PatternType.OUTCOME_TENDENCY,
                supporting_startups=["A", "B", "C"], support_count=2,
                confidence=PatternConfidence.LOW,
            )

    def test_supporters_must_be_unique(self):
        with self.assertRaises(ValidationError):
            ReferenceClassPattern(
                id="RCP-01", text="x", pattern_type=PatternType.OUTCOME_TENDENCY,
                supporting_startups=["A", "A"], support_count=2,
                confidence=PatternConfidence.LOW,
            )

    def test_id_pattern_is_enforced(self):
        with self.assertRaises(ValidationError):
            ReferenceClassPattern(
                id="RCP-1", text="x", pattern_type=PatternType.OUTCOME_TENDENCY,
                supporting_startups=["A", "B"], support_count=2,
                confidence=PatternConfidence.LOW,
            )

    def test_text_rejects_predictive_language(self):
        with self.assertRaises(ValidationError):
            ReferenceClassPattern(
                id="RCP-01", text="startups here have a 70% chance of success",
                pattern_type=PatternType.OUTCOME_TENDENCY,
                supporting_startups=["A", "B"], support_count=2,
                confidence=PatternConfidence.LOW,
            )


class SummaryNarrativeTests(unittest.TestCase):
    def test_no_dropped_candidates_omits_middle_sentence(self):
        text = build_summary_narrative(
            total_comparables=5, continued_count=3, ended_count=1, unclear_count=1,
            dropped_count=0,
        )
        self.assertEqual(
            text,
            "Among the 5 verified comparable startups retrieved for this idea, 3 had "
            "continued outcomes, 1 had ended outcomes, and 1 remained unclear. This "
            "sample is search-derived and is not a statistically representative "
            "population of similar startups.",
        )

    def test_dropped_candidates_add_neutral_middle_sentence(self):
        text = build_summary_narrative(
            total_comparables=5, continued_count=3, ended_count=1, unclear_count=1,
            dropped_count=2,
        )
        self.assertIn(
            "2 further candidate(s) were excluded during verification or relevance "
            "filtering.",
            text,
        )
        self.assertNotIn("unverifiable or insufficiently related", text)

    def test_summary_counts_must_be_consistent(self):
        with self.assertRaises(ValidationError):
            ReferenceClassSummary(
                total_comparables=2,
                by_outcome={StartupOutcome.ACQUIRED: 2},
                continued_count=1, ended_count=0, unclear_count=0, dropped_count=0,
                narrative="Among the 2 verified comparable startups retrieved for this "
                "idea, 2 had continued outcomes, 0 had ended outcomes, and 0 remained "
                "unclear. This sample is search-derived and is not a statistically "
                "representative population of similar startups.",
            )

    def test_by_outcome_sum_must_equal_total(self):
        with self.assertRaises(ValidationError):
            ReferenceClassSummary(
                total_comparables=3,
                by_outcome={StartupOutcome.ACQUIRED: 2},
                continued_count=2, ended_count=0, unclear_count=0, dropped_count=0,
                narrative="ok text placeholder that is descriptive only",
            )


class ReferenceClassTests(unittest.TestCase):
    def test_minimal_available_reference_class(self):
        rc = _reference_class(comparables=[_comparable()])
        self.assertEqual(rc.summary.total_comparables, 1)
        self.assertEqual(rc.llm_calls, 0)

    def test_llm_calls_default_is_zero(self):
        self.assertEqual(_reference_class().llm_calls, 0)

    def test_comparable_evidence_must_resolve_in_store(self):
        with self.assertRaises(ValidationError):
            _reference_class(
                comparables=[_comparable(evidence_ids=["E-404"])],
            )

    def test_dropped_candidate_evidence_must_resolve_in_store(self):
        with self.assertRaises(ValidationError):
            _reference_class(
                dropped=[
                    DroppedCandidate(
                        name="Ghost", reason=DropReason.NO_EVIDENCE_RETRIEVED,
                        detail="nothing retrieved", evidence_ids=["E-404"],
                    )
                ],
            )

    def test_pattern_may_only_cite_included_comparables(self):
        with self.assertRaises(ValidationError):
            _reference_class(
                comparables=[_comparable(name="Startup A")],
                patterns=[
                    ReferenceClassPattern(
                        id="RCP-01",
                        text="2 of the retrieved comparables were acquired by incumbents",
                        pattern_type=PatternType.OUTCOME_TENDENCY,
                        supporting_startups=["Startup A", "Ghost"], support_count=2,
                        confidence=PatternConfidence.LOW,
                    )
                ],
            )

    def test_pattern_ids_must_be_unique(self):
        pat = lambda: ReferenceClassPattern(  # noqa: E731
            id="RCP-01", text="2 retrieved comparables were acquired",
            pattern_type=PatternType.OUTCOME_TENDENCY,
            supporting_startups=["Startup A", "Startup B"], support_count=2,
            confidence=PatternConfidence.LOW,
        )
        with self.assertRaises(ValidationError):
            _reference_class(
                comparables=[
                    _comparable(name="Startup A", evidence_ids=["E-001"]),
                    _comparable(name="Startup B", evidence_ids=["E-002"]),
                ],
                patterns=[pat(), pat()],
            )

    def test_no_provider_status_requires_empty_result(self):
        rc = _reference_class(status=ReferenceClassStatus.UNAVAILABLE_NO_PROVIDER,
                              discovery=0, verification=0)
        self.assertEqual(rc.comparables, [])
        with self.assertRaises(ValidationError):
            _reference_class(status=ReferenceClassStatus.UNAVAILABLE_NO_PROVIDER,
                             discovery=1, verification=0)
        with self.assertRaises(ValidationError):
            _reference_class(status=ReferenceClassStatus.UNAVAILABLE_NO_PROVIDER,
                             discovery=0, verification=0, comparables=[_comparable()])

    def test_no_matches_status_allows_searches_but_no_comparables(self):
        rc = _reference_class(status=ReferenceClassStatus.UNAVAILABLE_NO_MATCHES,
                              discovery=3, verification=0)
        self.assertEqual(rc.comparables, [])
        with self.assertRaises(ValidationError):
            _reference_class(status=ReferenceClassStatus.UNAVAILABLE_NO_MATCHES,
                             comparables=[_comparable()])

    def test_partial_status_is_not_model_validated(self):
        # Correction #4: PARTIAL is an engine invariant; the model just accepts it.
        rc = _reference_class(
            status=ReferenceClassStatus.PARTIAL,
            comparables=[_comparable()],
            dropped=[
                DroppedCandidate(
                    name="Ghost", reason=DropReason.NOT_VERIFIED_AS_COMPANY,
                    detail="unverifiable",
                )
            ],
        )
        self.assertEqual(rc.status, ReferenceClassStatus.PARTIAL)

    def test_search_counts_are_hard_capped(self):
        with self.assertRaises(ValidationError):
            _reference_class(discovery=MAX_DISCOVERY_QUERIES + 1)
        with self.assertRaises(ValidationError):
            _reference_class(verification=MAX_VERIFICATION_SEARCHES + 1)

    def test_comparables_are_hard_capped(self):
        many = [
            _comparable(name=f"S{i}", evidence_ids=["E-001"])
            for i in range(MAX_COMPARABLES + 1)
        ]
        with self.assertRaises(ValidationError):
            _reference_class(comparables=many)


class ConstantsTests(unittest.TestCase):
    def test_similarity_weights_sum_to_one(self):
        self.assertTrue(math.isclose(sum(SIMILARITY_WEIGHTS.values()), 1.0, abs_tol=1e-9))

    def test_similarity_weights_match_approved_values(self):
        self.assertEqual(
            SIMILARITY_WEIGHTS,
            {
                SimilarityDimension.PROBLEM: 0.25,
                SimilarityDimension.CUSTOMER: 0.20,
                SimilarityDimension.INDUSTRY: 0.20,
                SimilarityDimension.PRODUCT_FORM: 0.15,
                SimilarityDimension.BUSINESS_MODEL: 0.15,
                SimilarityDimension.GEOGRAPHY: 0.05,
            },
        )

    def test_pattern_support_constants(self):
        self.assertEqual(PATTERN_MIN_SUPPORT, 2)
        self.assertEqual(PATTERN_MEDIUM_CONFIDENCE_MIN_SUPPORT, 3)

    def test_budget_constants(self):
        self.assertEqual(MAX_COMPARABLES, 8)
        self.assertEqual(MAX_DISCOVERY_QUERIES, 4)
        self.assertEqual(MAX_VERIFICATION_SEARCHES, 8)

    def test_polarity_map_covers_every_outcome(self):
        self.assertEqual(set(POLARITY_BY_OUTCOME), set(StartupOutcome))

    def test_unresolved_field_order_is_complete_and_unique(self):
        self.assertEqual(set(UNRESOLVED_FIELD_ORDER), set(UnresolvedField))
        self.assertEqual(len(UNRESOLVED_FIELD_ORDER), len(set(UNRESOLVED_FIELD_ORDER)))


if __name__ == "__main__":
    unittest.main()
