from datetime import datetime
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer
)

from reportlab.lib.styles import getSampleStyleSheet
from models.agent_result import (
    CTOAgentResult,
    InvestorAgentResult,
    MarketingAgentResult,
    ProductAgentResult,
)
from models.decision import SummaryResult


def generate_pdf(
    startup_idea,
    startup_health_score,
    investor_analysis: InvestorAgentResult,
    cto_analysis: CTOAgentResult,
    marketing_analysis: MarketingAgentResult,
    product_analysis: ProductAgentResult,
    summary_analysis: SummaryResult,
    ranked_assumptions=None,
    sensitivity_result=None,
    validation_plan=None,
):

    pdf_path = "startup_report.pdf"

    doc = SimpleDocTemplate(pdf_path)

    styles = getSampleStyleSheet()

    content = []

    # ==================================================
    # TITLE
    # ==================================================

    content.append(
        Paragraph(
            "AI Startup Boardroom Report",
            styles["Title"]
        )
    )

    content.append(Spacer(1, 20))

    content.append(
        Paragraph(
            f"Generated On: {datetime.now().strftime('%d-%m-%Y %H:%M')}",
            styles["BodyText"]
        )
    )

    content.append(Spacer(1, 20))

    # ==================================================
    # STARTUP IDEA
    # ==================================================

    content.append(
        Paragraph(
            "Startup Idea",
            styles["Heading2"]
        )
    )

    content.append(
        Paragraph(
            startup_idea,
            styles["BodyText"]
        )
    )

    content.append(Spacer(1, 15))

    # ==================================================
    # HEALTH SCORE
    # ==================================================

    content.append(
        Paragraph(
            "Startup Health Score",
            styles["Heading2"]
        )
    )

    content.append(
        Paragraph(
            f"{startup_health_score}/100",
            styles["BodyText"]
        )
    )

    content.append(Spacer(1, 15))

    # ==================================================
    # INVESTOR ANALYSIS
    # ==================================================

    content.append(
        Paragraph(
            "Investor Analysis",
            styles["Heading2"]
        )
    )
    
    investor_table = Table(
        [
            ["Metric", "Score"],
            ["Market", investor_analysis.market_score],
            ["Revenue", investor_analysis.revenue_score],
            ["Scalability", investor_analysis.scalability_score],
            ["Risk Management", investor_analysis.risk_management_score]
        ]
    )

    investor_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.grey),
            ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
            ("GRID", (0,0), (-1,-1), 1, colors.black),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold")
        ])
    )

    content.append(investor_table)

    content.append(Spacer(1, 10))

    content.append(
        Paragraph(
            "Strengths",
            styles["Heading3"]
        )
    )

    for item in investor_analysis.strengths:
        content.append(
            Paragraph(
                f"✓ {item}",
                styles["BodyText"]
            )
        )

    content.append(Spacer(1, 10))

    content.append(
        Paragraph(
            "Weaknesses",
            styles["Heading3"]
        )
    )

    for item in investor_analysis.weaknesses:
        content.append(
            Paragraph(
                f"⚠ {item}",
                styles["BodyText"]
            )
        )

    content.append(Spacer(1, 20))

    # ==================================================
    # CTO ANALYSIS
    # ==================================================

    content.append(
        Paragraph(
            "CTO Analysis",
            styles["Heading2"]
        )
    )

    cto_table = Table(
        [
            ["Metric", "Score"],
            ["Technical Feasibility", cto_analysis.technical_feasibility_score],
            ["Scalability", cto_analysis.scalability_score],
            ["Infrastructure Simplicity", cto_analysis.infrastructure_simplicity_score],
            ["Security Posture", cto_analysis.security_posture_score],
            ["Cost Efficiency", cto_analysis.cost_efficiency_score]
        ]
    )
    cto_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.grey),
            ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
            ("GRID", (0,0), (-1,-1), 1, colors.black),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold")
        ])
    )

    content.append(cto_table)

    content.append(Spacer(1, 10))

    content.append(
        Paragraph(
            "Strengths",
            styles["Heading3"]
        )
    )

    for item in cto_analysis.strengths:
        content.append(
            Paragraph(
                f"✓ {item}",
                styles["BodyText"]
            )
        )

    content.append(Spacer(1, 10))

    content.append(
        Paragraph(
            "Weaknesses",
            styles["Heading3"]
        )
    )

    for item in cto_analysis.weaknesses:
        content.append(
            Paragraph(
                f"⚠ {item}",
                styles["BodyText"]
            )
        )

    content.append(Spacer(1, 20))

    # ==================================================
    # MARKETING ANALYSIS
    # ==================================================

    content.append(
        Paragraph(
            "Marketing Analysis",
            styles["Heading2"]
        )
    )

    marketing_table = Table(
        [
            ["Metric", "Score"],
            ["Acquisition", marketing_analysis.customer_acquisition_score],
            ["Brand", marketing_analysis.brand_differentiation_score],
            ["Growth", marketing_analysis.growth_potential_score],
            ["Go-To-Market", marketing_analysis.go_to_market_score],
            ["Retention", marketing_analysis.retention_score]
        ]
    )
    marketing_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.grey),
            ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
            ("GRID", (0,0), (-1,-1), 1, colors.black),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold")
        ])
    )
    content.append(marketing_table)

    content.append(Spacer(1, 10))

    content.append(
        Paragraph(
            "Strengths",
            styles["Heading3"]
        )
    )

    for item in marketing_analysis.strengths:
        content.append(
            Paragraph(
                f"✓ {item}",
                styles["BodyText"]
            )
        )

    content.append(Spacer(1, 10))

    content.append(
        Paragraph(
            "Weaknesses",
            styles["Heading3"]
        )
    )

    for item in marketing_analysis.weaknesses:
        content.append(
            Paragraph(
                f"⚠ {item}",
                styles["BodyText"]
            )
        )

    content.append(Spacer(1, 20))

    # ==================================================
    # PRODUCT ANALYSIS
    # ==================================================

    content.append(
        Paragraph(
            "Product Analysis",
            styles["Heading2"]
        )
    )

    product_table = Table(
        [
            ["Metric", "Score"],
            ["Market Fit", product_analysis.product_market_fit_score],
            ["UX", product_analysis.user_experience_score],
            ["Differentiation", product_analysis.feature_differentiation_score],
            ["Retention", product_analysis.retention_score],
            ["Vision", product_analysis.product_vision_score]
        ]
    )
    product_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.grey),
            ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
            ("GRID", (0,0), (-1,-1), 1, colors.black),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold")
        ])
    )

    content.append(product_table)

    content.append(Spacer(1, 10))

    content.append(
        Paragraph(
            "Strengths",
            styles["Heading3"]
        )
    )

    for item in product_analysis.strengths:
        content.append(
            Paragraph(
                f"✓ {item}",
                styles["BodyText"]
            )
        )

    content.append(Spacer(1, 10))

    content.append(
        Paragraph(
            "Weaknesses",
            styles["Heading3"]
        )
    )

    for item in product_analysis.weaknesses:
        content.append(
            Paragraph(
                f"⚠ {item}",
                styles["BodyText"]
            )
        )

    content.append(Spacer(1, 20))

    # ==================================================
    # KEY ASSUMPTIONS
    # ==================================================

    content.append(
        Paragraph(
            "Key Assumptions",
            styles["Heading2"]
        )
    )

    if ranked_assumptions:
        assumptions_rows = [
            ["#", "Assumption", "Impact", "Uncertainty", "Criticality", "Evidence"]
        ]
        for item in ranked_assumptions:
            assumptions_rows.append([
                str(item.rank),
                Paragraph(item.text, styles["BodyText"]),
                str(item.impact),
                str(item.uncertainty),
                str(item.criticality),
                item.evidence_status.value.replace("_", " ").title(),
            ])

        assumptions_table = Table(
            assumptions_rows,
            colWidths=[18, 210, 40, 60, 55, 70]
        )
        assumptions_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.grey),
                ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
                ("GRID", (0,0), (-1,-1), 1, colors.black),
                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                ("VALIGN", (0,0), (-1,-1), "TOP"),
            ])
        )

        content.append(assumptions_table)
        content.append(Spacer(1, 10))

        critical = [item for item in ranked_assumptions if item.decision_critical]
        if critical:
            content.append(
                Paragraph(
                    "Decision-critical: "
                    + "; ".join(f"#{item.rank} {item.text}" for item in critical),
                    styles["BodyText"]
                )
            )
        else:
            content.append(
                Paragraph(
                    "No assumption reached the decision-critical threshold.",
                    styles["BodyText"]
                )
            )
    else:
        content.append(
            Paragraph(
                "No structured assumptions were produced for this run.",
                styles["BodyText"]
            )
        )

    content.append(Spacer(1, 20))

    # ==================================================
    # SENSITIVITY ANALYSIS
    # ==================================================

    content.append(
        Paragraph(
            "Sensitivity Analysis",
            styles["Heading2"]
        )
    )

    content.append(
        Paragraph(
            "Hypothetical failure scenarios - not predictions and not probabilities. "
            "Each row asks how the boardroom score would move if a decision-critical "
            "assumption proved false, using a fixed penalty model.",
            styles["BodyText"]
        )
    )

    content.append(Spacer(1, 8))

    if sensitivity_result is not None and sensitivity_result.scenarios:
        sensitivity_rows = [
            ["Assumption (if it proves false)", "Score: base -> scenario", "Delta", "Band change"]
        ]
        for scenario in sensitivity_result.scenarios:
            if scenario.mapping_status.value == "unmapped":
                score_cell = "unmapped"
                delta_cell = "-"
                band_cell = "not mapped"
            else:
                score_cell = (
                    f"{scenario.current_boardroom_score} -> "
                    f"{scenario.scenario_boardroom_score}"
                )
                delta_cell = str(scenario.score_delta)
                band_cell = (
                    f"{scenario.current_band} -> {scenario.scenario_band}"
                    if scenario.band_changed
                    else "no change"
                )
            sensitivity_rows.append([
                Paragraph(scenario.assumption_text, styles["BodyText"]),
                Paragraph(score_cell, styles["BodyText"]),
                delta_cell,
                Paragraph(band_cell, styles["BodyText"]),
            ])

        sensitivity_table = Table(
            sensitivity_rows,
            colWidths=[200, 110, 40, 110]
        )
        sensitivity_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.grey),
                ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
                ("GRID", (0,0), (-1,-1), 1, colors.black),
                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                ("VALIGN", (0,0), (-1,-1), "TOP"),
            ])
        )
        content.append(sensitivity_table)
        content.append(Spacer(1, 8))

        band_changers = [s for s in sensitivity_result.scenarios if s.band_changed]
        if band_changers:
            content.append(
                Paragraph(
                    "Failure scenarios that change the investment band: "
                    + "; ".join(s.assumption_text for s in band_changers),
                    styles["BodyText"]
                )
            )
        else:
            content.append(
                Paragraph(
                    "No modeled failure scenario changes the investment band.",
                    styles["BodyText"]
                )
            )
    else:
        content.append(
            Paragraph(
                "No decision-critical assumptions were available to stress-test.",
                styles["BodyText"]
            )
        )

    content.append(Spacer(1, 20))

    # ==================================================
    # FOUNDER VALIDATION PLAN
    # ==================================================

    content.append(
        Paragraph(
            "Founder Validation Plan",
            styles["Heading2"]
        )
    )

    content.append(
        Paragraph(
            "Suggested first tests to de-risk the load-bearing assumptions. "
            "Methods and success thresholds are suggestions, not universal benchmarks.",
            styles["BodyText"]
        )
    )

    content.append(Spacer(1, 8))

    if validation_plan is not None and validation_plan.items:
        validation_rows = [
            ["#", "Priority", "Assumption", "Method", "Success signal", "Sample"]
        ]
        for item in validation_plan.items:
            validation_rows.append([
                str(item.rank),
                item.priority.value,
                Paragraph(item.assumption_text, styles["BodyText"]),
                Paragraph(item.validation_method, styles["BodyText"]),
                Paragraph(item.success_signal, styles["BodyText"]),
                Paragraph(item.recommended_sample, styles["BodyText"]),
            ])

        validation_table = Table(
            validation_rows,
            colWidths=[16, 52, 104, 88, 122, 70]
        )
        validation_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.grey),
                ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
                ("GRID", (0,0), (-1,-1), 1, colors.black),
                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                ("VALIGN", (0,0), (-1,-1), "TOP"),
            ])
        )
        content.append(validation_table)
    else:
        content.append(
            Paragraph(
                "No structured assumptions were produced for this run.",
                styles["BodyText"]
            )
        )

    content.append(Spacer(1, 20))

    # ==================================================
    # FINAL VERDICT
    # ==================================================

    content.append(
        Paragraph(
            "Final Boardroom Verdict",
            styles["Heading2"]
        )
    )

    content.append(
        Paragraph(
            summary_analysis.final_verdict,
            styles["BodyText"]
        )
    )

    # ==================================================
    # BUILD PDF
    # ==================================================

    doc.build(content)

    return pdf_path
