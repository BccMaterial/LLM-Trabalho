import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

SYSTEM_PROMPT = """
Você é um agente de agendamentos para avaliações neuropsicológicas.
Responda em português, seja objetivo e solicite apenas as informações
necessárias para realizar um agendamento. Quando ainda não houver dados
suficientes, explique quais informações estão faltando.
""".strip()

TEST_MESSAGE = "Olá! Esta é uma mensagem de teste do agente."


def send_test_message() -> str:
    """Send a test message to the configured language model."""
    client = OpenAI(
        base_url=os.environ["LLM_BASE_URL"],
        api_key=os.environ["OPENAI_API_KEY"],
    )
    response = client.chat.completions.create(
        model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": TEST_MESSAGE},
        ],
    )
    return response.choices[0].message.content or ""


if __name__ == "__main__":
    print("Enviando mensagem de teste para o modelo de linguagem...")
    print(send_test_message())
