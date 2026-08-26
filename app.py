from agents.investor import investor_agent
from agents.cto import cto_agent
from agents.summary import summary_agent
from services.scoring import calculate_boardroom_score
from agents.marketing import marketing_agent
from agents.product import product_agent
from models.startup import StartupIdea
from services.report_generator import (
    display_investor_report,
    display_cto_report,
    display_marketing_report,
    display_product_report,
    display_boardroom_report
)

startup_idea = StartupIdea(description="""
AI-powered tutoring platform for college students.
The platform generates personalized study plans,
practice questions, and interview preparation material.
Revenue model is monthly subscription.
""".strip()).description

analysis = investor_agent(startup_idea)
cto_analysis = cto_agent(startup_idea)
marketing_analysis = marketing_agent(startup_idea)
product_analysis = product_agent(startup_idea)

boardroom_context = f"""
INVESTOR ANALYSIS:

{analysis}

CTO ANALYSIS:

{cto_analysis}

MARKETING ANALYSIS:

{marketing_analysis}

PRODUCT ANALYSIS:

{product_analysis}
"""

summary = summary_agent(boardroom_context)

startup_health_score = calculate_boardroom_score(
    analysis,
    cto_analysis,
    marketing_analysis,
    product_analysis,
)

display_investor_report(
    analysis,
    startup_health_score
)

display_cto_report(
    cto_analysis
)

display_marketing_report(
    marketing_analysis
)

display_product_report(
    product_analysis
)

display_boardroom_report(
    summary
)
