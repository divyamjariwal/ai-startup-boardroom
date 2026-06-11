from agents.investor import investor_agent
from agents.cto import cto_agent
from agents.summary import summary_agent
from services.scoring import calculate_startup_score
from services.report_generator import (
    display_investor_report,
    display_cto_report,
    display_boardroom_report
)

startup_idea = """
AI-powered tutoring platform for college students.
The platform generates personalized study plans,
practice questions, and interview preparation material.
Revenue model is monthly subscription.
"""

analysis = investor_agent(startup_idea)
cto_analysis = cto_agent(startup_idea)

boardroom_context = f"""
INVESTOR ANALYSIS:

{analysis}

CTO ANALYSIS:

{cto_analysis}
"""

summary = summary_agent(boardroom_context)

startup_health_score = calculate_startup_score(analysis)

display_investor_report(
    analysis,
    startup_health_score
)

display_cto_report(
    cto_analysis
)

display_boardroom_report(
    summary
)