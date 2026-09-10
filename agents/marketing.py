from agents.base_agent import run_agent
from models.agent_result import MarketingAgentResult


def marketing_agent(startup_idea: str, evidence: str = "") -> MarketingAgentResult:

    return run_agent(
        "prompts/marketing_prompt.txt",
        f"<STARTUP_INPUT>\n{startup_idea}\n</STARTUP_INPUT>\n<RESEARCH_EVIDENCE>\n{evidence}\n</RESEARCH_EVIDENCE>",
        MarketingAgentResult,
    )
