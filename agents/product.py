from agents.base_agent import run_agent
from models.agent_result import ProductAgentResult


def product_agent(startup_idea: str) -> ProductAgentResult:

    return run_agent(
        "prompts/product_prompt.txt",
        startup_idea,
        ProductAgentResult,
    )
