from datetime import datetime
from reportlab.platypus import Table, TableStyle
from reportlab.lib import colors

from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer
)

from reportlab.lib.styles import getSampleStyleSheet


def generate_pdf(
    startup_idea,
    startup_health_score,
    investor_analysis,
    cto_analysis,
    marketing_analysis,
    product_analysis,
    summary_analysis
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
            ["Market", investor_analysis["market_score"]],
            ["Revenue", investor_analysis["revenue_score"]],
            ["Scalability", investor_analysis["scalability_score"]],
            ["Risk", investor_analysis["risk_score"]]
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

    for item in investor_analysis["strengths"]:
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

    for item in investor_analysis["weaknesses"]:
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
            ["Technical Feasibility", cto_analysis["technical_feasibility_score"]],
            ["Scalability", cto_analysis["scalability_score"]],
            ["Infrastructure", cto_analysis["infrastructure_complexity_score"]],
            ["Security", cto_analysis["security_risk_score"]],
            ["Development Cost", cto_analysis["development_cost_score"]]
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

    for item in cto_analysis["strengths"]:
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

    for item in cto_analysis["weaknesses"]:
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
            ["Acquisition", marketing_analysis["customer_acquisition_score"]],
            ["Brand", marketing_analysis["brand_differentiation_score"]],
            ["Growth", marketing_analysis["growth_potential_score"]],
            ["Go-To-Market", marketing_analysis["go_to_market_score"]],
            ["Retention", marketing_analysis["retention_score"]]
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

    for item in marketing_analysis["strengths"]:
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

    for item in marketing_analysis["weaknesses"]:
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
            ["Market Fit", product_analysis["product_market_fit_score"]],
            ["UX", product_analysis["user_experience_score"]],
            ["Differentiation", product_analysis["feature_differentiation_score"]],
            ["Retention", product_analysis["retention_score"]],
            ["Vision", product_analysis["product_vision_score"]]
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

    for item in product_analysis["strengths"]:
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

    for item in product_analysis["weaknesses"]:
        content.append(
            Paragraph(
                f"⚠ {item}",
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
            summary_analysis["final_verdict"],
            styles["BodyText"]
        )
    )

    # ==================================================
    # BUILD PDF
    # ==================================================

    doc.build(content)

    return pdf_path