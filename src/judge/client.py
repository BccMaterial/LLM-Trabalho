"""Cliente do juiz LLM, com credenciais separadas das do agente."""

from __future__ import annotations

import os

from dotenv import load_dotenv
from openai import OpenAI

from .rubric import JUDGE_MAX_TOKENS, JUDGE_TEMPERATURE, ROOT

REQUIRED_ENV = (
    "JUDGE_LLM_BASE_URL",
    "JUDGE_LLM_API_KEY",
    "JUDGE_LLM_MODEL",
)


def missing_env() -> list[str]:
    load_dotenv(ROOT / ".env")
    return [name for name in REQUIRED_ENV if not os.environ.get(name)]


def create_client() -> OpenAI:
    missing = missing_env()
    if missing and "JUDGE_LLM_API_KEY" in missing and os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY foi renomeada. Configure JUDGE_LLM_API_KEY "
            "(e JUDGE_LLM_BASE_URL/JUDGE_LLM_MODEL) para o juiz."
        )
    if missing:
        raise RuntimeError(f"variáveis ausentes para o juiz: {', '.join(missing)}")
    return OpenAI(
        base_url=os.environ["JUDGE_LLM_BASE_URL"],
        api_key=os.environ["JUDGE_LLM_API_KEY"],
        timeout=60,
        max_retries=2,
    )


def judge_identity() -> dict[str, str]:
    """Identificação da rodada sem expor valores de credenciais."""
    load_dotenv(ROOT / ".env")
    missing = missing_env()
    if missing:
        raise RuntimeError(f"variáveis ausentes para o juiz: {', '.join(missing)}")
    return {
        "model": os.environ["JUDGE_LLM_MODEL"],
        "provider": "endpoint OpenAI-compatível configurado em JUDGE_LLM_BASE_URL",
        "temperature": str(JUDGE_TEMPERATURE),
        "max_tokens": str(JUDGE_MAX_TOKENS),
        "env_keys": ", ".join(REQUIRED_ENV),
    }


def judge_message(prompt: str) -> str:
    response = create_client().chat.completions.create(
        model=os.environ["JUDGE_LLM_MODEL"],
        messages=[{"role": "user", "content": prompt}],
        temperature=JUDGE_TEMPERATURE,
        max_tokens=JUDGE_MAX_TOKENS,
    )
    return response.choices[0].message.content or ""
