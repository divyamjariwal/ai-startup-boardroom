from agents.base_agent import run_agent


def cto_agent(startup_idea):

    return run_agent(
        "prompts/cto_prompt.txt",
        startup_idea
    )