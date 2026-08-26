from agents.base_agent import run_agent
from models.debate import DebateResult


def debate_agent(boardroom_context: str) -> DebateResult:

    return run_agent(
        "prompts/debate_prompt.txt",
        boardroom_context,
        DebateResult,
    )
