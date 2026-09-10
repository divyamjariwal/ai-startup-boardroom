from agents.base_agent import run_agent
from models.agent_result import ProductAgentResult


def product_agent(startup_idea: str, evidence: str = "") -> ProductAgentResult:

    return run_agent(
        "prompts/product_prompt.txt",
        f"<STARTUP_INPUT>\n{startup_idea}\n</STARTUP_INPUT>\n<RESEARCH_EVIDENCE>\n{evidence}\n</RESEARCH_EVIDENCE>",
        ProductAgentResult,
    )
