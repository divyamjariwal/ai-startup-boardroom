from groq import Groq
from dotenv import load_dotenv
import os
import json
import logging
from typing import TypeVar

from pydantic import BaseModel, ValidationError

load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

logger = logging.getLogger(__name__)

AgentResultT = TypeVar("AgentResultT", bound=BaseModel)


class AgentOutputValidationError(Exception):
    """Raised when an LLM response does not match its required contract."""

def repair_json(content):

    content = content.strip()

    if content.startswith("```json"):
        content = content.replace("```json", "")

    if content.startswith("```"):
        content = content.replace("```", "")

    if content.endswith("```"):
        content = content[:-3]

    content = content.strip()

    if content.startswith("{") and not content.endswith("}"):
        content += "\n}"

    return content

def run_agent(prompt_file: str, user_input: str, result_model: type[AgentResultT]) -> AgentResultT:

    with open(prompt_file, "r", encoding="utf-8") as file:
        system_prompt = file.read()

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": user_input
            }
        ]
    )

    content = response.choices[0].message.content


    try:
        content = repair_json(content)
        payload = json.loads(content)
        return result_model.model_validate(payload)
    except (json.JSONDecodeError, ValidationError) as error:
        logger.warning(
            "Agent response failed validation for prompt '%s': %s",
            prompt_file,
            error,
        )
        raise AgentOutputValidationError(
            "The agent returned an invalid response. Please run the analysis again."
        ) from error
