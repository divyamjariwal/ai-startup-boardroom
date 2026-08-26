from agents.base_agent import run_agent
from models.decision import SummaryResult


def summary_agent(boardroom_context: str) -> SummaryResult:

    return run_agent(
        "prompts/summary_prompt.txt",
        boardroom_context,
        SummaryResult,
    )
