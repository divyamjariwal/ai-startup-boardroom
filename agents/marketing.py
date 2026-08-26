from agents.base_agent import run_agent
from models.agent_result import MarketingAgentResult


def marketing_agent(startup_idea: str) -> MarketingAgentResult:

    return run_agent(
        "prompts/marketing_prompt.txt",
        startup_idea,
        MarketingAgentResult,
    )
