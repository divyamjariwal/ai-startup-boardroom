from agents.base_agent import run_agent


def investor_agent(startup_idea):

    return run_agent(
        "prompts/investor_prompt.txt",
        startup_idea
    )