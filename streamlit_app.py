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

st.set_page_config(
    page_title="AI Startup Boardroom",
    page_icon="🚀",
    layout="wide"
)

st.title("🚀 AI Startup Boardroom")

startup_idea = st.text_area(
    "Enter your Startup Idea",
    height=200
)

if st.button("Analyze Startup"):

    if startup_idea.strip():

        startup_idea = StartupIdea(description=startup_idea.strip()).description

        with st.spinner("Boardroom is analyzing the startup..."):

            investor_analysis = investor_agent(startup_idea)

            cto_analysis = cto_agent(startup_idea)

            marketing_analysis = marketing_agent(startup_idea)

            product_analysis = product_agent(startup_idea)

            boardroom_context = f"""
            INVESTOR ANALYSIS:
            {investor_analysis.model_dump_json(indent=2)}

            CTO ANALYSIS:
            {cto_analysis.model_dump_json(indent=2)}

            MARKETING ANALYSIS:
            {marketing_analysis.model_dump_json(indent=2)}

            PRODUCT ANALYSIS:
            {product_analysis.model_dump_json(indent=2)}
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
                consensus_status = "✅ Strong Consensus"

            elif consensus_score >= 50:
                consensus_status = "⚠️ Moderate Consensus"

            else:
                consensus_status = "🚨 Major Disagreement"

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

            pdf_file = generate_pdf(
                startup_idea,
                startup_health_score,
                investor_analysis,
                cto_analysis,
                marketing_analysis,
                product_analysis,
                summary_analysis
            )

        st.divider()

        st.subheader("🚀 Startup Health Score")

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

        st.info(investment_decision)

        st.progress(
            startup_health_score / 100
        )

        tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
            [
                "💰 Investor",
                "⚙️ CTO",
                "📈 Marketing",
                "🎯 Product",
                "🤝 Debate",
                "🏛️ Verdict"
            ]
        )

        with tab1:
            display_agent_card(
            title="Investor Analysis",
            icon="💰",
            scores={
                "Market": investor_analysis.market_score,
                "Revenue": investor_analysis.revenue_score,
                "Scalability": investor_analysis.scalability_score,
                "Risk Management": investor_analysis.risk_management_score,
            },
            strengths=investor_analysis.strengths,
            weaknesses=investor_analysis.weaknesses,
            recommendation=investor_analysis.recommendation
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
                icon="⚙️",
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
                icon="📈",
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
                icon="🎯",
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

            st.subheader("🤝 Boardroom Debate")
            st.metric(
                "Boardroom Consensus Score",
                f"{consensus_score}%"
            )

            st.caption(consensus_status)

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

            st.success("✅ Areas of Agreement")

            for item in debate_analysis.agreements:
                st.write(f"• {item}")

            st.warning("⚠ Areas of Disagreement")

            for item in debate_analysis.disagreements:
                st.write(f"• {item}")

            st.error("🚨 Major Risks")

            for item in debate_analysis.major_risks:
                st.write(f"• {item}")

            st.info("🏆 Strongest Arguments")

            for item in debate_analysis.strongest_arguments:
                st.write(f"• {item}")

            st.subheader("📝 Debate Summary")

            st.success(
                debate_analysis.debate_summary
            )

        st.divider()
        
        with tab6:
            st.subheader("🏛️ Boardroom Verdict")

            st.success(
                summary_analysis.final_verdict
            )

            with open(pdf_file, "rb") as file:

                st.download_button(
                    label="📄 Download Boardroom Report",
                    data=file,
                    file_name="startup_report.pdf",
                    mime="application/pdf"
                )

    else:
        st.warning("Please enter a startup idea.")
