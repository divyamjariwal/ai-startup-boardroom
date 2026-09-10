from agents.base_agent import run_agent
from models.agent_result import InvestorAgentResult


def investor_agent(startup_idea: str, evidence: str = "") -> InvestorAgentResult:

    return run_agent(
        "prompts/investor_prompt.txt",
        f"<STARTUP_INPUT>\n{startup_idea}\n</STARTUP_INPUT>\n<RESEARCH_EVIDENCE>\n{evidence}\n</RESEARCH_EVIDENCE>",
        InvestorAgentResult,
    )
