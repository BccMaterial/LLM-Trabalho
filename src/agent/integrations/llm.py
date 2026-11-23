import os
import time

from openai import APIConnectionError, APIStatusError, OpenAI, RateLimitError

from ...network_security import validate_service_base_url
from ..observability import mark_span_error, set_token_usage, tracer
from ..tools import TOOLS
from ..workflows.execution import MAX_EXTERNAL_CALL_SECONDS

MAX_LLM_RETRIES = 5
RETRY_BACKOFF_SECONDS = 5


def create_client() -> OpenAI:
    base_url = validate_service_base_url(
        os.environ["LLM_BASE_URL"],
        setting_name="LLM_BASE_URL",
    )
    return OpenAI(
        base_url=base_url,
        api_key=os.environ["LLM_API_KEY"],
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
    model = os.environ["LLM_MODEL"]
    with tracer().start_as_current_span(
        "chat",
        attributes={
            "gen_ai.operation.name": "chat",
            "gen_ai.provider.name": "openai",
            "gen_ai.request.model": model,
        },
    ) as span:
        try:
            response = _request_with_retry(
                llm_client,
                messages,
                max_tokens=max_tokens,
                timeout_seconds=timeout_seconds,
                tool_definitions=tool_definitions,
            )
        except Exception as error:
            mark_span_error(span, error)
            raise

        response_model = getattr(response, "model", None)
        if isinstance(response_model, str):
            span.set_attribute("gen_ai.response.model", response_model)
        usage = getattr(response, "usage", None)
        set_token_usage(span, usage)
        choices = getattr(response, "choices", None) or []
        if choices:
            finish_reason = getattr(choices[0], "finish_reason", None)
            if isinstance(finish_reason, str):
                span.set_attribute("gen_ai.response.finish_reasons", [finish_reason])
        return response


def _request_with_retry(
    llm_client: OpenAI,
    messages: list[dict],
    max_tokens: int | None = None,
    timeout_seconds: float = MAX_EXTERNAL_CALL_SECONDS,
    tool_definitions: list[dict] = TOOLS,
):
    deadline = time.monotonic() + timeout_seconds
    model = os.environ["LLM_MODEL"]
    for attempt in range(MAX_LLM_RETRIES):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise RuntimeError("LLM excedeu o tempo máximo da execução.")
        try:
            request_options = {"max_tokens": max_tokens} if max_tokens else {}
            request_client = llm_client.with_options(timeout=remaining)
            return request_client.chat.completions.create(
                model=model,
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
