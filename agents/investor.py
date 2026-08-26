from agents.base_agent import run_agent
from models.agent_result import InvestorAgentResult


def investor_agent(startup_idea: str) -> InvestorAgentResult:

    return run_agent(
        "prompts/investor_prompt.txt",
        startup_idea,
        InvestorAgentResult,
    )
