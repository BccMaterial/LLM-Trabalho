import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

PROMPT_PATH = (
    Path(__file__).resolve().parents[2] / "prompts" / "atendente_v1.txt"
)

# This versioned prompt uses intent routing and source-grounded responses.
# Its target contract is docs/io.md; it prevents guessed clinic facts and
# unconfirmed bookings. Tool calls and deterministic schema validation are
# not implemented in this prototype yet.
SYSTEM_PROMPT = PROMPT_PATH.read_text(encoding="utf-8")

TEST_MESSAGE = "Olá! Esta é uma mensagem de teste do agente."


def send_test_message() -> str:
    """Send a test message to the configured language model."""
    client = OpenAI(
        base_url=os.environ["LLM_BASE_URL"],
        api_key=os.environ["OPENAI_API_KEY"],
    )
    response = client.chat.completions.create(
        model=os.environ["LLM_MODEL"],
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": TEST_MESSAGE},
        ],
    )
    return response.choices[0].message.content or ""


if __name__ == "__main__":
    print("Enviando mensagem de teste para o modelo de linguagem...")
    print(send_test_message())
