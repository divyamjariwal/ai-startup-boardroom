import os

# The reference-class discovery tests assert the deterministic
# UNAVAILABLE_NO_PROVIDER fallback when no research provider is configured.
# That must hold regardless of what a developer's local .env contains, so
# strip it before any test module (which may import agents.base_agent and
# trigger load_dotenv()) runs.
os.environ.pop("TAVILY_API_KEY", None)
