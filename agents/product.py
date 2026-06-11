from agents.base_agent import run_agent


def product_agent(startup_idea):

    return run_agent(
        "prompts/product_prompt.txt",
        startup_idea
    )