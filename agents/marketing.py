from agents.base_agent import run_agent


def marketing_agent(startup_idea):

    return run_agent(
        "prompts/marketing_prompt.txt",
        startup_idea
    )