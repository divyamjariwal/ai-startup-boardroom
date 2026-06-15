from agents.base_agent import run_agent


def debate_agent(boardroom_context):

    return run_agent(
        "prompts/debate_prompt.txt",
        boardroom_context
    )