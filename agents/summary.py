from agents.base_agent import run_agent


def summary_agent(boardroom_context):

    return run_agent(
        "prompts/summary_prompt.txt",
        boardroom_context
    )