import os
import time

from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError

from ..tools import TOOLS
from ..workflows.execution import MAX_EXTERNAL_CALL_SECONDS

MAX_LLM_RETRIES = 5
RETRY_BACKOFF_SECONDS = 5


def create_client() -> OpenAI:
    return OpenAI(
        base_url=os.environ["LLM_BASE_URL"],
        api_key=os.environ["OPENAI_API_KEY"],
        timeout=MAX_EXTERNAL_CALL_SECONDS,
        max_retries=0,
    )


def request_with_retry(
    llm_client: OpenAI,
    messages: list[dict],
    max_tokens: int | None = None,
    timeout_seconds: float = MAX_EXTERNAL_CALL_SECONDS,
    tool_definitions: list[dict] = TOOLS,
):
    deadline = time.monotonic() + timeout_seconds
    for attempt in range(MAX_LLM_RETRIES):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError("LLM excedeu o tempo máximo da execução.")
        try:
            request_options = {"max_tokens": max_tokens} if max_tokens else {}
            request_client = llm_client.with_options(timeout=remaining)
            return request_client.chat.completions.create(
                model=os.environ["LLM_MODEL"],
                messages=messages,
                tools=tool_definitions,
                **request_options,
            )
        except RateLimitError as error:
            if attempt == MAX_LLM_RETRIES - 1:
                raise RuntimeError(
                    f"LLM continuou limitado após {MAX_LLM_RETRIES} tentativas: "
                    f"{error.response.text}"
                ) from error

            retry_after = error.response.headers.get("retry-after")
            try:
                delay = float(retry_after) if retry_after else 0
            except ValueError:
                delay = 0
            delay = max(delay, RETRY_BACKOFF_SECONDS * (2**attempt))
            if delay >= deadline - time.monotonic():
                raise RuntimeError(
                    "LLM continuou limitado e o tempo máximo da execução foi atingido."
                ) from error
            print(
                f"Limite do LLM atingido. Tentando novamente em {delay:g}s "
                f"({attempt + 1}/{MAX_LLM_RETRIES})..."
            )
            time.sleep(delay)
        except APIStatusError as error:
            raise RuntimeError(
                f"LLM retornou HTTP {error.status_code}: {error.response.text}"
            ) from error
        except APIConnectionError as error:
            raise RuntimeError(f"Não foi possível conectar ao LLM: {error}") from error
