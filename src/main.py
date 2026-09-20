import os

from openai import OpenAI

client = OpenAI(
    base_url=os.environ["LLM_BASE_URL"],  # o provedor que vocês escolheram
    api_key=os.environ["OPENAI_API_KEY"],
)

if __name__ == "__main__":
    print("Hello, World!")
