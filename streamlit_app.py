import json
import os

import streamlit as st
from components.agent_cards import display_agent_card
from services.scoring import (
    calculate_boardroom_score,
    calculate_cto_score,
    calculate_investor_score,
    calculate_marketing_score,
    calculate_product_score,
    get_investment_decision,
)
from services.pdf_generator import generate_pdf
from agents.investor import investor_agent
from agents.cto import cto_agent
from agents.marketing import marketing_agent
from agents.product import product_agent
from agents.summary import summary_agent
from agents.debate import debate_agent
from components.charts import display_radar_chart
from components.dashboard import display_executive_dashboard
from models.startup import StartupIdea
from models.evidence import ResearchCategory
from services.research import ResearchEngine, evidence_package
from services.verifier import evidence_coverage, verify_claim
from services.assumption_engine import rank_assumptions
from services.sensitivity_engine import run_sensitivity
from services.validation_engine import build_validation_plan
from services.idea_profile import build_idea_profile
from services.reference_discovery import discover_reference_class
from services.reference_outcomes import verify_outcomes
from services.reference_class_engine import build_reference_class
from components.theme import (
    PRIMARY,
    PRIMARY_STRONG,
    SURFACE_ELEVATED,
    BORDER,
    PRIMARY_TINT,
    PRIMARY_SHADOW,
    CARD_SHADOW,
    badge_html,
)

st.set_page_config(
    page_title="AI Startup Boardroom",
    layout="wide"
)

_CSS = """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }

    #MainMenu, footer, [data-testid="stToolbar"] { visibility: hidden; height: 0; }

    .block-container {
        padding-top: 2.25rem;
        padding-bottom: 3rem;
        max-width: 1180px;
    }

    /* ---------- Hero ---------- */
    .boardroom-hero {
        padding: 2.25rem 2.5rem;
        margin-bottom: 1.75rem;
        border-radius: 20px;
        background: linear-gradient(120deg, __PRIMARY_STRONG__ 0%, __PRIMARY__ 100%);
        color: #FFFFFF;
        box-shadow: 0 12px 28px -14px __CARD_SHADOW__;
    }
    .boardroom-hero .eyebrow {
        text-transform: uppercase;
        letter-spacing: 0.14em;
        font-size: 0.72rem;
        font-weight: 600;
        opacity: 0.85;
        margin-bottom: 0.35rem;
    }
    .boardroom-hero h1 {
        font-size: 2.1rem;
        font-weight: 800;
        letter-spacing: -0.02em;
        margin: 0 0 0.5rem 0;
        color: #FFFFFF;
    }
    .boardroom-hero p {
        font-size: 1rem;
        font-weight: 400;
        opacity: 0.92;
        margin: 0;
        max-width: 720px;
        line-height: 1.5;
    }

    /* ---------- Headings ---------- */
    h1, h2, h3 { letter-spacing: -0.01em; font-weight: 700; }
    h2 { font-size: 1.4rem !important; }
    h3 { font-size: 1.12rem !important; }

    /* ---------- Cards / containers ---------- */
    [data-testid="stVerticalBlockBorderWrapper"] {
        border-radius: 16px !important;
        background: __SURFACE_ELEVATED__;
        border: 1px solid __BORDER__ !important;
        box-shadow: 0 6px 18px -12px __CARD_SHADOW__;
    }
    div[data-testid="stExpander"] {
        border-radius: 14px;
        background: __SURFACE_ELEVATED__;
        border: 1px solid __BORDER__;
    }

    /* ---------- Metrics ---------- */
    [data-testid="stMetric"] {
        background: __SURFACE_ELEVATED__;
        border: 1px solid __BORDER__;
        border-radius: 14px;
        padding: 0.9rem 1rem 0.7rem 1rem;
    }
    [data-testid="stMetricLabel"] { font-weight: 600; }

    /* ---------- Buttons ---------- */
    .stButton > button {
        border-radius: 10px;
        font-weight: 600;
        padding: 0.6rem 1.4rem;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
        border: none;
    }
    .stButton > button[kind="primary"] {
        background: __PRIMARY_STRONG__;
        box-shadow: 0 6px 16px -6px __PRIMARY_SHADOW__;
    }
    .stButton > button:hover { transform: translateY(-1px); }
    div[data-testid="stDownloadButton"] > button {
        border-radius: 10px;
        font-weight: 600;
    }

    /* ---------- Text input ---------- */
    .stTextArea textarea {
        border-radius: 12px;
        font-size: 0.98rem;
    }

    /* ---------- Tabs ---------- */
    .stTabs [data-baseweb="tab-list"] {
        gap: 4px;
        border-bottom: 1px solid __BORDER__;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 10px 10px 0 0;
        padding: 0.55rem 1.05rem;
        font-weight: 600;
        font-size: 0.9rem;
    }
    .stTabs [aria-selected="true"] {
        background-color: __PRIMARY_TINT__;
        color: __PRIMARY__;
    }

    /* ---------- Alerts ---------- */
    div[data-testid="stAlert"] {
        border-radius: 12px;
    }

    hr { margin: 1.1rem 0; opacity: 0.4; }
    </style>
    """
_CSS = (
    _CSS.replace("__PRIMARY_STRONG__", PRIMARY_STRONG)
    .replace("__PRIMARY_SHADOW__", PRIMARY_SHADOW)
    .replace("__PRIMARY_TINT__", PRIMARY_TINT)
    .replace("__PRIMARY__", PRIMARY)
    .replace("__SURFACE_ELEVATED__", SURFACE_ELEVATED)
    .replace("__CARD_SHADOW__", CARD_SHADOW)
    .replace("__BORDER__", BORDER)
)

st.markdown(_CSS, unsafe_allow_html=True)

st.markdown(
    """
    <div class="boardroom-hero">
        <div class="eyebrow">AI-Powered Decision Support</div>
        <h1>AI Startup Boardroom</h1>
        <p>Evaluate a startup idea the way a real board would - four specialist perspectives,
        evidence-checked claims, ranked assumptions, and a founder-ready validation plan,
        all in one report.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

with st.container(border=True):
    st.markdown("#### Describe your startup idea")
    startup_idea = st.text_area(
        "Enter your Startup Idea",
        height=180,
        placeholder="e.g. A subscription meal-kit delivery service for busy urban professionals, "
                     "offering pre-portioned ingredients and 20-minute recipes...",
        label_visibility="collapsed",
    )
    analyze_clicked = st.button("Analyze Startup", type="primary", use_container_width=True)

if analyze_clicked:

    if startup_idea.strip():

        startup_idea = StartupIdea(description=startup_idea.strip()).description

        with st.spinner("Boardroom is analyzing the startup..."):

            research_run = ResearchEngine().run(startup_idea)
            st.session_state["research_run"] = research_run

            idea_profile = build_idea_profile(startup_idea)
            reference_discovery = discover_reference_class(idea_profile)
            reference_verification = verify_outcomes(reference_discovery)
            reference_class = build_reference_class(reference_verification)
            st.session_state["reference_class"] = reference_class

            investor_analysis = investor_agent(startup_idea, evidence_package(research_run.store, [ResearchCategory.MARKET, ResearchCategory.PRICING, ResearchCategory.COMPETITORS, ResearchCategory.BUSINESS_MODEL]))

            cto_analysis = cto_agent(startup_idea, evidence_package(research_run.store, [ResearchCategory.TECHNOLOGY, ResearchCategory.REGULATORY]))

            marketing_analysis = marketing_agent(startup_idea, evidence_package(research_run.store, [ResearchCategory.CUSTOMERS, ResearchCategory.COMPETITORS, ResearchCategory.PRICING, ResearchCategory.INDUSTRY_TRENDS]))

            product_analysis = product_agent(startup_idea, evidence_package(research_run.store, [ResearchCategory.CUSTOMERS, ResearchCategory.COMPETITORS, ResearchCategory.TECHNOLOGY]))

            for analysis in (investor_analysis, cto_analysis, marketing_analysis, product_analysis):
                analysis.verified_claims = [verify_claim(claim, research_run.store) for claim in analysis.claims]

            ranked_assumptions = rank_assumptions(
                [investor_analysis, cto_analysis, marketing_analysis, product_analysis],
                [
                    claim
                    for analysis in (investor_analysis, cto_analysis, marketing_analysis, product_analysis)
                    for claim in analysis.verified_claims
                ],
            )

            def _condensed_analysis(analysis):
                # Debate/summary agents only need scores + interpretation, not the
                # verbose claims/verified_claims/assumptions payloads - including those
                # routinely pushed the combined request over the Groq per-minute token limit.
                data = analysis.model_dump(mode="json")
                for bulky_field in ("claims", "verified_claims", "assumptions"):
                    data.pop(bulky_field, None)
                return json.dumps(data, indent=2)

            boardroom_context = f"""
            INVESTOR ANALYSIS:
            {_condensed_analysis(investor_analysis)}

            CTO ANALYSIS:
            {_condensed_analysis(cto_analysis)}

            MARKETING ANALYSIS:
            {_condensed_analysis(marketing_analysis)}

            PRODUCT ANALYSIS:
            {_condensed_analysis(product_analysis)}
            """
            debate_analysis = debate_agent(
                boardroom_context
            )
            consensus_score = int(
                (
                    len(debate_analysis.agreements)
                    /
                    (
                        len(debate_analysis.agreements)
                        +
                        len(debate_analysis.disagreements)
                    )
                )
                * 100
            )
            if consensus_score >= 80:
                consensus_status = "Strong Consensus"
                consensus_status_key = "good"

            elif consensus_score >= 50:
                consensus_status = "Moderate Consensus"
                consensus_status_key = "warning"

            else:
                consensus_status = "Major Disagreement"
                consensus_status_key = "critical"

            summary_analysis = summary_agent(
                boardroom_context
            )

            investor_score = calculate_investor_score(investor_analysis)
            cto_score = calculate_cto_score(cto_analysis)
            marketing_score = calculate_marketing_score(marketing_analysis)
            product_score = calculate_product_score(product_analysis)

            agent_scores = {
                "Investor": investor_score,
                "CTO": cto_score,
                "Marketing": marketing_score,
                "Product": product_score
            }

            strongest_agent = max(
                agent_scores,
                key=agent_scores.get
            )

            weakest_agent = min(
                agent_scores,
                key=agent_scores.get
            )

            startup_health_score = calculate_boardroom_score(
                investor_analysis,
                cto_analysis,
                marketing_analysis,
                product_analysis
            )

            investment_decision = get_investment_decision(
                startup_health_score
            )

            sensitivity_result = run_sensitivity(
                investor_analysis,
                cto_analysis,
                marketing_analysis,
                product_analysis,
                startup_health_score,
                investment_decision,
                ranked_assumptions,
            )

            validation_plan = build_validation_plan(ranked_assumptions)

            pdf_file = generate_pdf(
                startup_idea,
                startup_health_score,
                investor_analysis,
                cto_analysis,
                marketing_analysis,
                product_analysis,
                summary_analysis,
                idea_profile,
                ranked_assumptions,
                sensitivity_result,
                validation_plan,
                reference_class
            )

        st.divider()

        st.subheader("Startup Health Score")

        st.metric(
            "Overall Score",
            f"{startup_health_score}/100"
        )
        display_executive_dashboard(
            investor_score,
            cto_score,
            marketing_score,
            product_score
        )

        col1, col2 = st.columns(2)

        with col1:
            st.success(
                f"""
        Strongest Perspective

        {strongest_agent}
        ({int(agent_scores[strongest_agent])}/100)
        """
            )

        with col2:
            st.warning(
                f"""
        Weakest Perspective

        {weakest_agent}
        ({int(agent_scores[weakest_agent])}/100)
        """
            )

        if startup_health_score >= 85:
            decision_status = "good"
        elif startup_health_score >= 70:
            decision_status = "warning"
        else:
            decision_status = "critical"
        st.markdown(badge_html(investment_decision, decision_status), unsafe_allow_html=True)

        st.progress(
            startup_health_score / 100
        )

        tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9, tab10, tab11 = st.tabs(
            [
                "Investor",
                "CTO",
                "Marketing",
                "Product",
                "Debate",
                "Verdict",
                "Evidence & Sources",
                "Assumptions",
                "Sensitivity",
                "Validation Plan",
                "Reference Class"
            ]
        )

        with tab1:
            display_agent_card(
            title="Investor Analysis",
            scores={
                "Market": investor_analysis.market_score,
                "Revenue": investor_analysis.revenue_score,
                "Scalability": investor_analysis.scalability_score,
                "Risk Management": investor_analysis.risk_management_score,
            },
            strengths=investor_analysis.strengths,
            weaknesses=investor_analysis.weaknesses,
            recommendation=investor_analysis.recommendation
            ,verified_claims=investor_analysis.verified_claims
            )

            display_radar_chart(
                "Investor Scores",
                {
                    "Market": investor_analysis.market_score,
                    "Revenue": investor_analysis.revenue_score,
                    "Scalability": investor_analysis.scalability_score,
                    "Risk Management": investor_analysis.risk_management_score,
                }
            )

        with tab2:
            display_agent_card(
                title="CTO Analysis",
                scores={
                    "Feasibility": cto_analysis.technical_feasibility_score,
                    "Scalability": cto_analysis.scalability_score,
                    "Infrastructure Simplicity": cto_analysis.infrastructure_simplicity_score,
                    "Security Posture": cto_analysis.security_posture_score,
                    "Cost Efficiency": cto_analysis.cost_efficiency_score,
                },
                strengths=cto_analysis.strengths,
                weaknesses=cto_analysis.weaknesses,
                recommendation=cto_analysis.recommendation
                ,verified_claims=cto_analysis.verified_claims
            )

            display_radar_chart(
                "CTO Scores",
                {
                    "Feasibility": cto_analysis.technical_feasibility_score,
                    "Scalability": cto_analysis.scalability_score,
                    "Infrastructure Simplicity": cto_analysis.infrastructure_simplicity_score,
                    "Security Posture": cto_analysis.security_posture_score,
                    "Cost Efficiency": cto_analysis.cost_efficiency_score,
                }
            )
        
        with tab3:
            display_agent_card(
                title="Marketing Analysis",
                scores={
                    "Acquisition": marketing_analysis.customer_acquisition_score,
                    "Brand": marketing_analysis.brand_differentiation_score,
                    "Growth": marketing_analysis.growth_potential_score,
                    "Go-To-Market": marketing_analysis.go_to_market_score,
                    "Retention": marketing_analysis.retention_score,
                },
                strengths=marketing_analysis.strengths,
                weaknesses=marketing_analysis.weaknesses,
                recommendation=marketing_analysis.recommendation
                ,verified_claims=marketing_analysis.verified_claims
            )

            display_radar_chart(
                "Marketing Scores",
                {
                    "Acquisition": marketing_analysis.customer_acquisition_score,
                    "Brand": marketing_analysis.brand_differentiation_score,
                    "Growth": marketing_analysis.growth_potential_score,
                    "Go-To-Market": marketing_analysis.go_to_market_score,
                    "Retention": marketing_analysis.retention_score,
                }
            )
        
        with tab4:
            display_agent_card(
                title="Product Analysis",
                scores={
                    "Market Fit": product_analysis.product_market_fit_score,
                    "UX": product_analysis.user_experience_score,
                    "Differentiation": product_analysis.feature_differentiation_score,
                    "Retention": product_analysis.retention_score,
                    "Vision": product_analysis.product_vision_score,
                },
                strengths=product_analysis.strengths,
                weaknesses=product_analysis.weaknesses,
                recommendation=product_analysis.recommendation
                ,verified_claims=product_analysis.verified_claims
            )

            display_radar_chart(
                "Product Scores",
                {
                    "Market Fit": product_analysis.product_market_fit_score,
                    "UX": product_analysis.user_experience_score,
                    "Differentiation": product_analysis.feature_differentiation_score,
                    "Retention": product_analysis.retention_score,
                    "Vision": product_analysis.product_vision_score,
                }
            )
        
        with tab5:

            st.subheader("Boardroom Debate")
            st.metric(
                "Boardroom Consensus Score",
                f"{consensus_score}%"
            )

            st.markdown(badge_html(consensus_status, consensus_status_key), unsafe_allow_html=True)

            st.progress(
                consensus_score / 100
            )

            # col1, col2, col3, col4 = st.columns(4)

            col1, col2 = st.columns(2)

            with col1:
                st.success(
                    f"""
            Consensus Level

            {len(debate_analysis.agreements)} Agreements
            """
                )

            with col2:
                st.warning(
                    f"""
            Debate Intensity

            {len(debate_analysis.disagreements)} Disagreements
            """
                )
            
            col1, col2 = st.columns(2)

            with col1:
                st.error(
                    f"""
            Risk Exposure

            {len(debate_analysis.major_risks)} Major Risks
            """
                )

            with col2:
                st.info(
                    f"""
            Argument Strength

            {len(debate_analysis.strongest_arguments)} Key Arguments
            """
                )

            st.success("Areas of Agreement")

            for item in debate_analysis.agreements:
                st.write(f"• {item}")

            st.warning("Areas of Disagreement")

            for item in debate_analysis.disagreements:
                st.write(f"• {item}")

            st.error("Major Risks")

            for item in debate_analysis.major_risks:
                st.write(f"• {item}")

            st.info("Strongest Arguments")

            for item in debate_analysis.strongest_arguments:
                st.write(f"• {item}")

            st.subheader("Debate Summary")

            st.success(
                debate_analysis.debate_summary
            )

        st.divider()
        
        with tab6:
            st.subheader("Boardroom Verdict")

            st.success(
                summary_analysis.final_verdict
            )

            with open(pdf_file, "rb") as file:

                st.download_button(
                    label="Download Boardroom Report",
                    data=file,
                    file_name=os.path.basename(pdf_file),
                    mime="application/pdf"
                )

        with tab7:
            st.subheader("Evidence & Sources")
            st.caption("Evidence Coverage measures how many agent factual claims have relevant evidence. It is not an accuracy score.")
            st.info(research_run.message)
            if research_run.status == "RESEARCH_UNAVAILABLE":
                st.warning("External evidence unavailable. Claims cannot be fully verified.")
            all_claims = [claim for analysis in (investor_analysis, cto_analysis, marketing_analysis, product_analysis) for claim in analysis.verified_claims]
            st.metric("Evidence Coverage", f"{evidence_coverage(all_claims)}%")
            for claim in all_claims:
                with st.expander(f"{claim.status.value.replace('_', ' ').title()}: {claim.text}"):
                    st.write(claim.verification_notes)
                    st.caption(f"Confidence: {claim.confidence:.0%} · Evidence: {', '.join(claim.source_evidence_ids) or 'None'}")
                    for evidence_id in claim.source_evidence_ids:
                        item = research_run.store.get(evidence_id)
                        if item:
                            st.markdown(f"[{item.title}]({item.source_url}) — {item.source_name} · {item.source_quality.value.title()}")
                            st.write(item.excerpt)
            st.subheader("Evidence by category")
            for category in ResearchCategory:
                items = research_run.store.list(category)
                if items:
                    with st.expander(f"{category.value.replace('_', ' ').title()} ({len(items)})"):
                        for item in items:
                            st.markdown(f"**{item.evidence_id} — [{item.title}]({item.source_url})**")
                            st.caption(f"{item.source_name} · {item.source_type.value} · quality: {item.source_quality.value}")
                            st.write(item.excerpt)

        with tab8:
            st.subheader("Decision-Critical Assumptions")
            st.caption(
                "Load-bearing assumptions the startup must get right, ranked by impact × uncertainty. "
                "Criticality (impact × uncertainty) of 16 or more is treated as decision-critical."
            )
            if not ranked_assumptions:
                st.info("No structured assumptions were produced for this run.")
            else:
                critical = [item for item in ranked_assumptions if item.decision_critical]
                st.metric(
                    "Decision-Critical Assumptions",
                    f"{len(critical)} of {len(ranked_assumptions)}"
                )
                for item in ranked_assumptions:
                    heading = f"#{item.rank} — {item.text}"
                    detail = (
                        f"Category: {item.category} · Impact: {item.impact}/5 · "
                        f"Uncertainty: {item.uncertainty}/5 · Criticality: {item.criticality} · "
                        f"Evidence: {item.evidence_status.value.replace('_', ' ').title()}"
                    )
                    if item.decision_critical:
                        st.error(heading)
                    else:
                        st.write(heading)
                    st.caption(detail)

        with tab9:
            st.subheader("Sensitivity — Failure Scenarios")
            st.caption(
                "Each row asks: if this decision-critical assumption proves false, how far "
                "does the boardroom score move? Scenario analysis — not a prediction, "
                "and not a probability."
            )
            if not sensitivity_result.scenarios:
                st.info("No decision-critical assumptions to stress-test for this run.")
            else:
                st.metric(
                    "Failure scenarios that change the investment band",
                    f"{sensitivity_result.band_changing_count} of {len(sensitivity_result.scenarios)}"
                )
                st.caption(
                    f"Current boardroom score: {sensitivity_result.current_boardroom_score}/100 "
                    f"· {sensitivity_result.current_band}"
                )
                for scenario in sensitivity_result.scenarios:
                    heading = f"If this assumption proves false: {scenario.assumption_text}"
                    if scenario.mapping_status.value == "unmapped":
                        st.write(heading)
                        st.caption(f"Unmapped — {scenario.note}")
                        continue
                    if scenario.band_changed:
                        st.error(heading)
                    else:
                        st.warning(heading)
                    st.caption(
                        f"{scenario.current_boardroom_score}/100 → "
                        f"{scenario.scenario_boardroom_score}/100 "
                        f"(Δ {scenario.score_delta}) · "
                        f"{scenario.current_band} → {scenario.scenario_band} · "
                        f"impact {scenario.impact}/5 · uncertainty {scenario.uncertainty}/5 · "
                        f"modeled penalty {round(scenario.scenario_penalty * 100, 1)}%"
                    )
                    st.caption(scenario.note)

        with tab10:
            st.subheader("Founder Validation Plan")
            st.caption(validation_plan.disclaimer)
            if not validation_plan.items:
                st.info("No structured assumptions were produced for this run.")
            else:
                for item in validation_plan.items:
                    st.markdown(
                        f"**#{item.rank} · {item.priority.value} · {item.assumption_text}**"
                    )
                    st.caption(
                        f"Evidence: {item.evidence_status.value.replace('_', ' ').title()} "
                        f"· Criticality: {item.criticality}"
                    )
                    st.write(f"• **Method:** {item.validation_method}")
                    st.write(f"• **Test question:** {item.test_question}")
                    st.write(f"• **Success signal:** {item.success_signal}")
                    st.write(f"• **Recommended sample:** {item.recommended_sample}")
                    st.write(f"• **Why:** {item.rationale}")
                    st.divider()

        with tab11:
            st.subheader("Historical Reference Class")
            st.caption(
                "Real past/current startups similar to this idea, and what appears to have "
                "happened to them. Descriptive evidence only — not a prediction, and kept "
                "separate from the boardroom score and assumptions."
            )
            st.info(reference_verification.message)

            if reference_class.status.value in ("unavailable_no_provider", "unavailable_no_matches"):
                st.warning(
                    "No reference class available for this run "
                    f"({reference_class.status.value.replace('_', ' ')})."
                )
            else:
                summary = reference_class.summary
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Comparables found", summary.total_comparables)
                col2.metric("Still going / exited well", summary.continued_count)
                col3.metric("Shut down / pivoted", summary.ended_count)
                col4.metric("Unclear outcome", summary.unclear_count)

                st.write(summary.narrative)
                st.caption(reference_class.disclaimer)

                if reference_class.patterns:
                    st.subheader("Recurring patterns")
                    for pattern in reference_class.patterns:
                        st.write(f"**{pattern.id}** ({pattern.confidence.value.title()}) — {pattern.text}")

                if reference_class.comparables:
                    st.subheader("Comparable startups")
                    for comparable in reference_class.comparables:
                        heading = (
                            f"{comparable.name} — similarity {comparable.similarity.total}/100 · "
                            f"{comparable.outcome.outcome.value.replace('_', ' ').title()}"
                        )
                        if comparable.outcome.outcome_year:
                            heading += f" ({comparable.outcome.outcome_year})"
                        with st.expander(heading):
                            st.write(comparable.outcome.rationale)
                            matched = ", ".join(
                                dim.value for dim in comparable.similarity.matched_dimensions
                            ) or "none"
                            st.caption(f"Matched dimensions: {matched}")
                            for evidence_id in comparable.evidence_ids:
                                item = reference_class.evidence_store.get(evidence_id)
                                if item:
                                    st.markdown(f"[{item.title}]({item.source_url}) — {item.source_name}")

                if reference_class.dropped_candidates:
                    st.caption(
                        "Candidates excluded: "
                        + "; ".join(
                            f"{dropped.name} ({dropped.reason.value.replace('_', ' ')})"
                            for dropped in reference_class.dropped_candidates
                        )
                    )

    else:
        st.warning("Please enter a startup idea.")
