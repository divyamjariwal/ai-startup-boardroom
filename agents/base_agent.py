from groq import Groq
from dotenv import load_dotenv
import os
import json
import traceback

load_dotenv()

client = Groq(
    api_key=os.getenv("GROQ_API_KEY")
)

def repair_json(content):

    content = content.strip()

    # Missing final closing brace
    if content.startswith("{") and not content.endswith("}"):
        content += "\n}"

    return content

def run_agent(prompt_file, user_input):

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

        return json.loads(content)

    except json.JSONDecodeError:

        print("\nJSON PARSING FAILED\n")
        print(content)

        raise