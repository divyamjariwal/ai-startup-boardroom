import re
from datetime import datetime

from reportlab.platypus import Table, TableStyle, PageBreak, KeepTogether
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

_SLUG_MAX_LEN = 40
_SLUG_INVALID_CHARS = re.compile(r"[^a-z0-9-]+")


def _build_filename(idea_profile) -> str:
    """Derive a readable report filename from the idea's keywords/industry."""

    words = list(idea_profile.keywords[:3])

    if not words:
        if idea_profile.industry and idea_profile.industry != "unspecified":
            words = [idea_profile.industry]
        else:
            words = ["startup"]

    slug = "-".join(words).lower().replace(" ", "-")
    slug = _SLUG_INVALID_CHARS.sub("-", slug).strip("-")

    if len(slug) > _SLUG_MAX_LEN:
        truncated = slug[:_SLUG_MAX_LEN]
        slug = truncated.rsplit("-", 1)[0] if "-" in truncated else truncated

    date_stamp = datetime.now().strftime("%Y-%m-%d")

    return f"{slug}-boardroom-report_{date_stamp}.pdf"


def generate_pdf(
    startup_idea,
    startup_health_score,
    investor_analysis: InvestorAgentResult,
    cto_analysis: CTOAgentResult,
    marketing_analysis: MarketingAgentResult,
    product_analysis: ProductAgentResult,
    summary_analysis: SummaryResult,
    idea_profile,
    ranked_assumptions=None,
    sensitivity_result=None,
    validation_plan=None,
    reference_class=None,
):

    pdf_path = _build_filename(idea_profile)

    doc = SimpleDocTemplate(pdf_path)

    styles = getSampleStyleSheet()

    content = []

    # ==================================================
    # TITLE
    # ==================================================

    title_section = []

    title_section.append(
        Paragraph(
            "AI Startup Boardroom Report",
            styles["Title"]
        )
    )

    title_section.append(Spacer(1, 20))

    title_section.append(
        Paragraph(
            f"Generated On: {datetime.now().strftime('%d-%m-%Y %H:%M')}",
            styles["BodyText"]
        )
    )

    content.append(KeepTogether(title_section))
    content.append(Spacer(1, 15))

    # ==================================================
    # STARTUP IDEA
    # ==================================================
    # Not wrapped in KeepTogether: this is a single free-text paragraph that
    # can run up to 10,000 characters, so it must be allowed to paginate
    # normally rather than being forced to fit (or overflow awkwardly from)
    # one KeepTogether block.

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

    health_section = []

    health_section.append(
        Paragraph(
            "Startup Health Score",
            styles["Heading2"]
        )
    )

    health_section.append(
        Paragraph(
            f"{startup_health_score}/100",
            styles["BodyText"]
        )
    )

    content.append(KeepTogether(health_section))

    # ==================================================
    # INVESTOR ANALYSIS
    # ==================================================
    # Each agent section below is grouped into one KeepTogether block so its
    # heading/table/strengths/weaknesses don't split across a page boundary.
    # No PageBreak between them: KeepTogether already pushes a block to a new
    # page only when it doesn't fit the remaining space, so multiple small
    # sections pack onto the same page instead of each wasting a full page.
    # A section whose own content is taller than one full page will still
    # spill onto a second page - that's a physical page-size limit, not a bug.

    content.append(PageBreak())

    investor_section = []

    investor_section.append(
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
        ],
        repeatRows=1
    )

    investor_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#4F46E5")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
            ("GRID", (0,0), (-1,-1), 1, colors.black),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold")
        ])
    )

    investor_section.append(investor_table)

    investor_section.append(Spacer(1, 10))

    investor_section.append(
        Paragraph(
            "Strengths",
            styles["Heading3"]
        )
    )

    for item in investor_analysis.strengths:
        investor_section.append(
            Paragraph(
                item,
                styles["BodyText"]
            )
        )

    investor_section.append(Spacer(1, 10))

    investor_section.append(
        Paragraph(
            "Weaknesses",
            styles["Heading3"]
        )
    )

    for item in investor_analysis.weaknesses:
        investor_section.append(
            Paragraph(
                item,
                styles["BodyText"]
            )
        )

    content.append(KeepTogether(investor_section))

    # ==================================================
    # CTO ANALYSIS
    # ==================================================

    cto_section = []

    cto_section.append(
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
        ],
        repeatRows=1
    )
    cto_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#4F46E5")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
            ("GRID", (0,0), (-1,-1), 1, colors.black),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold")
        ])
    )

    cto_section.append(cto_table)

    cto_section.append(Spacer(1, 10))

    cto_section.append(
        Paragraph(
            "Strengths",
            styles["Heading3"]
        )
    )

    for item in cto_analysis.strengths:
        cto_section.append(
            Paragraph(
                item,
                styles["BodyText"]
            )
        )

    cto_section.append(Spacer(1, 10))

    cto_section.append(
        Paragraph(
            "Weaknesses",
            styles["Heading3"]
        )
    )

    for item in cto_analysis.weaknesses:
        cto_section.append(
            Paragraph(
                item,
                styles["BodyText"]
            )
        )

    content.append(KeepTogether(cto_section))

    # ==================================================
    # MARKETING ANALYSIS
    # ==================================================

    marketing_section = []

    marketing_section.append(
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
        ],
        repeatRows=1
    )
    marketing_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#4F46E5")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
            ("GRID", (0,0), (-1,-1), 1, colors.black),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold")
        ])
    )
    marketing_section.append(marketing_table)

    marketing_section.append(Spacer(1, 10))

    marketing_section.append(
        Paragraph(
            "Strengths",
            styles["Heading3"]
        )
    )

    for item in marketing_analysis.strengths:
        marketing_section.append(
            Paragraph(
                item,
                styles["BodyText"]
            )
        )

    marketing_section.append(Spacer(1, 10))

    marketing_section.append(
        Paragraph(
            "Weaknesses",
            styles["Heading3"]
        )
    )

    for item in marketing_analysis.weaknesses:
        marketing_section.append(
            Paragraph(
                item,
                styles["BodyText"]
            )
        )

    content.append(KeepTogether(marketing_section))

    # ==================================================
    # PRODUCT ANALYSIS
    # ==================================================

    product_section = []

    product_section.append(
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
        ],
        repeatRows=1
    )
    product_table.setStyle(
        TableStyle([
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#4F46E5")),
            ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
            ("GRID", (0,0), (-1,-1), 1, colors.black),
            ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold")
        ])
    )

    product_section.append(product_table)

    product_section.append(Spacer(1, 10))

    product_section.append(
        Paragraph(
            "Strengths",
            styles["Heading3"]
        )
    )

    for item in product_analysis.strengths:
        product_section.append(
            Paragraph(
                item,
                styles["BodyText"]
            )
        )

    product_section.append(Spacer(1, 10))

    product_section.append(
        Paragraph(
            "Weaknesses",
            styles["Heading3"]
        )
    )

    for item in product_analysis.weaknesses:
        product_section.append(
            Paragraph(
                item,
                styles["BodyText"]
            )
        )

    content.append(KeepTogether(product_section))

    # ==================================================
    # KEY ASSUMPTIONS
    # ==================================================
    # Explicit break: separates the four specialist analyses from the
    # tabular risk/assumptions/validation/reference-class material.

    content.append(PageBreak())

    assumptions_section = []

    assumptions_section.append(
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
            colWidths=[18, 210, 40, 60, 55, 70],
            repeatRows=1
        )
        assumptions_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#4F46E5")),
                ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
                ("GRID", (0,0), (-1,-1), 1, colors.black),
                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                ("VALIGN", (0,0), (-1,-1), "TOP"),
            ])
        )

        assumptions_section.append(assumptions_table)
        assumptions_section.append(Spacer(1, 10))

        critical = [item for item in ranked_assumptions if item.decision_critical]
        if critical:
            assumptions_section.append(
                Paragraph(
                    "Decision-critical: "
                    + "; ".join(f"#{item.rank} {item.text}" for item in critical),
                    styles["BodyText"]
                )
            )
        else:
            assumptions_section.append(
                Paragraph(
                    "No assumption reached the decision-critical threshold.",
                    styles["BodyText"]
                )
            )
    else:
        assumptions_section.append(
            Paragraph(
                "No structured assumptions were produced for this run.",
                styles["BodyText"]
            )
        )

    content.append(KeepTogether(assumptions_section))

    # ==================================================
    # SENSITIVITY ANALYSIS
    # ==================================================

    sensitivity_section = []

    sensitivity_section.append(
        Paragraph(
            "Sensitivity Analysis",
            styles["Heading2"]
        )
    )

    sensitivity_section.append(
        Paragraph(
            "Hypothetical failure scenarios - not predictions and not probabilities. "
            "Each row asks how the boardroom score would move if a decision-critical "
            "assumption proved false, using a fixed penalty model.",
            styles["BodyText"]
        )
    )

    sensitivity_section.append(Spacer(1, 8))

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
            colWidths=[200, 110, 40, 110],
            repeatRows=1
        )
        sensitivity_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#4F46E5")),
                ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
                ("GRID", (0,0), (-1,-1), 1, colors.black),
                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                ("VALIGN", (0,0), (-1,-1), "TOP"),
            ])
        )
        sensitivity_section.append(sensitivity_table)
        sensitivity_section.append(Spacer(1, 8))

        band_changers = [s for s in sensitivity_result.scenarios if s.band_changed]
        if band_changers:
            sensitivity_section.append(
                Paragraph(
                    "Failure scenarios that change the investment band: "
                    + "; ".join(s.assumption_text for s in band_changers),
                    styles["BodyText"]
                )
            )
        else:
            sensitivity_section.append(
                Paragraph(
                    "No modeled failure scenario changes the investment band.",
                    styles["BodyText"]
                )
            )
    else:
        sensitivity_section.append(
            Paragraph(
                "No decision-critical assumptions were available to stress-test.",
                styles["BodyText"]
            )
        )

    content.append(KeepTogether(sensitivity_section))

    # ==================================================
    # FOUNDER VALIDATION PLAN
    # ==================================================

    validation_section = []

    validation_section.append(
        Paragraph(
            "Founder Validation Plan",
            styles["Heading2"]
        )
    )

    validation_section.append(
        Paragraph(
            "Suggested first tests to de-risk the load-bearing assumptions. "
            "Methods and success thresholds are suggestions, not universal benchmarks.",
            styles["BodyText"]
        )
    )

    validation_section.append(Spacer(1, 8))

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
            colWidths=[16, 52, 104, 88, 122, 70],
            repeatRows=1
        )
        validation_table.setStyle(
            TableStyle([
                ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#4F46E5")),
                ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
                ("GRID", (0,0), (-1,-1), 1, colors.black),
                ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                ("VALIGN", (0,0), (-1,-1), "TOP"),
            ])
        )
        validation_section.append(validation_table)
    else:
        validation_section.append(
            Paragraph(
                "No structured assumptions were produced for this run.",
                styles["BodyText"]
            )
        )

    content.append(KeepTogether(validation_section))

    # ==================================================
    # REFERENCE CLASS (HISTORICAL COMPARABLES)
    # ==================================================

    if reference_class is not None:
        reference_section = []

        reference_section.append(
            Paragraph(
                "Historical Reference Class",
                styles["Heading2"]
            )
        )

        reference_section.append(
            Paragraph(
                "Real past/current startups similar to this idea, and what appears to have "
                "happened to them. Descriptive evidence only, kept separate from the "
                "boardroom score and assumptions.",
                styles["BodyText"]
            )
        )

        reference_section.append(Spacer(1, 8))

        if reference_class.status.value in ("unavailable_no_provider", "unavailable_no_matches"):
            reference_section.append(
                Paragraph(
                    "No reference class available for this run "
                    f"({reference_class.status.value.replace('_', ' ')}).",
                    styles["BodyText"]
                )
            )
        else:
            reference_section.append(
                Paragraph(reference_class.summary.narrative, styles["BodyText"])
            )
            reference_section.append(Spacer(1, 8))

            if reference_class.comparables:
                comparable_rows = [
                    ["Startup", "Similarity", "Outcome", "Year"]
                ]
                for comparable in reference_class.comparables:
                    comparable_rows.append([
                        Paragraph(comparable.name, styles["BodyText"]),
                        str(comparable.similarity.total),
                        comparable.outcome.outcome.value.replace("_", " ").title(),
                        str(comparable.outcome.outcome_year or "-"),
                    ])

                comparable_table = Table(
                    comparable_rows,
                    colWidths=[190, 60, 130, 40],
                    repeatRows=1
                )
                comparable_table.setStyle(
                    TableStyle([
                        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#4F46E5")),
                        ("TEXTCOLOR", (0,0), (-1,0), colors.whitesmoke),
                        ("GRID", (0,0), (-1,-1), 1, colors.black),
                        ("FONTNAME", (0,0), (-1,0), "Helvetica-Bold"),
                        ("VALIGN", (0,0), (-1,-1), "TOP"),
                    ])
                )
                reference_section.append(comparable_table)
                reference_section.append(Spacer(1, 8))

            if reference_class.patterns:
                reference_section.append(
                    Paragraph(
                        "Recurring patterns: "
                        + " | ".join(
                            f"{p.id}: {p.text}" for p in reference_class.patterns
                        ),
                        styles["BodyText"]
                    )
                )

        content.append(KeepTogether(reference_section))

    # ==================================================
    # FINAL VERDICT
    # ==================================================
    # Explicit break: keeps the closing verdict from being glued to the tail
    # end of whatever table precedes it.

    content.append(PageBreak())

    verdict_section = []

    verdict_section.append(
        Paragraph(
            "Final Boardroom Verdict",
            styles["Heading2"]
        )
    )

    verdict_section.append(
        Paragraph(
            summary_analysis.final_verdict,
            styles["BodyText"]
        )
    )

    content.append(KeepTogether(verdict_section))

    # ==================================================
    # BUILD PDF
    # ==================================================

    doc.build(content)

    return pdf_path
