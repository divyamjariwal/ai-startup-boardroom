import streamlit as st
from components.agent_cards import display_agent_card
from services.scoring import (calculate_boardroom_score,get_investment_decision)
from services.pdf_generator import generate_pdf
from agents.investor import investor_agent
from agents.cto import cto_agent
from agents.marketing import marketing_agent
from agents.product import product_agent
from agents.summary import summary_agent
from components.charts import display_radar_chart

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

        with st.spinner("Boardroom is analyzing the startup..."):

            investor_analysis = investor_agent(startup_idea)

            cto_analysis = cto_agent(startup_idea)

            marketing_analysis = marketing_agent(startup_idea)

            product_analysis = product_agent(startup_idea)

            boardroom_context = f"""
            INVESTOR ANALYSIS:
            {investor_analysis}

            CTO ANALYSIS:
            {cto_analysis}

            MARKETING ANALYSIS:
            {marketing_analysis}

            PRODUCT ANALYSIS:
            {product_analysis}
            """
            summary_analysis = summary_agent(
                boardroom_context
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
        st.info(investment_decision)

        st.progress(
            startup_health_score / 100
        )

        tab1, tab2, tab3, tab4, tab5 = st.tabs(
            [
                "💰 Investor",
                "⚙️ CTO",
                "📈 Marketing",
                "🎯 Product",
                "🏛️ Verdict"
            ]
        )

        with tab1:
            display_agent_card(
            title="Investor Analysis",
            icon="💰",
            scores={
                "Market": investor_analysis["market_score"],
                "Revenue": investor_analysis["revenue_score"],
                "Scalability": investor_analysis["scalability_score"],
                "Risk": investor_analysis["risk_score"]
            },
            strengths=investor_analysis["strengths"],
            weaknesses=investor_analysis["weaknesses"],
            recommendation=investor_analysis["recommendation"]
            )

            display_radar_chart(
                "Investor Scores",
                {
                    "Market": investor_analysis["market_score"],
                    "Revenue": investor_analysis["revenue_score"],
                    "Scalability": investor_analysis["scalability_score"],
                    "Risk": investor_analysis["risk_score"]
                }
            )

        with tab2:
            display_agent_card(
                title="CTO Analysis",
                icon="⚙️",
                scores={
                    "Feasibility": cto_analysis["technical_feasibility_score"],
                    "Scalability": cto_analysis["scalability_score"],
                    "Security": cto_analysis["security_risk_score"],
                    "Cost": cto_analysis["development_cost_score"]
                },
                strengths=cto_analysis["strengths"],
                weaknesses=cto_analysis["weaknesses"],
                recommendation=cto_analysis["recommendation"]
            )

            display_radar_chart(
                "CTO Scores",
                {
                    "Feasibility": cto_analysis["technical_feasibility_score"],
                    "Scalability": cto_analysis["scalability_score"],
                    "Security": cto_analysis["security_risk_score"],
                    "Cost": cto_analysis["development_cost_score"]
                }
            )
        
        with tab3:
            display_agent_card(
                title="Marketing Analysis",
                icon="📈",
                scores={
                    "Acquisition": marketing_analysis["customer_acquisition_score"],
                    "Brand": marketing_analysis["brand_differentiation_score"],
                    "Growth": marketing_analysis["growth_potential_score"],
                    "Retention": marketing_analysis["retention_score"]
                },
                strengths=marketing_analysis["strengths"],
                weaknesses=marketing_analysis["weaknesses"],
                recommendation=marketing_analysis["recommendation"]
            )

            display_radar_chart(
                "Marketing Scores",
                {
                    "Acquisition": marketing_analysis["customer_acquisition_score"],
                    "Brand": marketing_analysis["brand_differentiation_score"],
                    "Growth": marketing_analysis["growth_potential_score"],
                    "Retention": marketing_analysis["retention_score"]
                }
            )
        
        with tab4:
            display_agent_card(
                title="Product Analysis",
                icon="🎯",
                scores={
                    "Market Fit": product_analysis["product_market_fit_score"],
                    "UX": product_analysis["user_experience_score"],
                    "Retention": product_analysis["retention_score"],
                    "Vision": product_analysis["product_vision_score"]
                },
                strengths=product_analysis["strengths"],
                weaknesses=product_analysis["weaknesses"],
                recommendation=product_analysis["recommendation"]
            )

            display_radar_chart(
                "Product Scores",
                {
                    "Market Fit": product_analysis["product_market_fit_score"],
                    "UX": product_analysis["user_experience_score"],
                    "Retention": product_analysis["retention_score"],
                    "Vision": product_analysis["product_vision_score"]
                }
            )

        st.divider()
        
        with tab5:
            st.subheader("🏛️ Boardroom Verdict")

            st.success(
                summary_analysis["final_verdict"]
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