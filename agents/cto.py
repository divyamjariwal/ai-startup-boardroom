from agents.base_agent import run_agent
from models.agent_result import CTOAgentResult


def cto_agent(startup_idea: str) -> CTOAgentResult:

    return run_agent(
        "prompts/cto_prompt.txt",
        startup_idea,
        CTOAgentResult,
    )
