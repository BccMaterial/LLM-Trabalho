import os
import random
import time

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    OpenAI,
    RateLimitError,
)

from ...network_security import validate_service_base_url
from ..observability import mark_span_error, set_token_usage, tracer
from ..tools import TOOLS
from ..workflows.execution import (
    MAX_EXTERNAL_CALL_SECONDS,
    ProviderTimeoutFailure,
    RateLimitFailure,
    RecoverableExecutionError,
)

MAX_LLM_RETRIES = 5
RETRY_BACKOFF_SECONDS = 1.0
MAX_RETRY_BACKOFF_SECONDS = 8.0
MAX_RETRY_AFTER_SECONDS = 5.0
RETRYABLE_STATUS_CODES = frozenset({408, 425, 429, 500, 502, 503, 504})


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


def _retry_delay(error: Exception, attempt: int, deadline: float) -> float | None:
    """Jitter exponencial respeitando Retry-After e o prazo restante."""
    headers = getattr(getattr(error, "response", None), "headers", {}) or {}
    retry_after = headers.get("retry-after") if hasattr(headers, "get") else None
    try:
        declared = float(retry_after) if retry_after else 0.0
    except (TypeError, ValueError):
        declared = 0.0
    backoff = min(
        RETRY_BACKOFF_SECONDS * (2**attempt),
        MAX_RETRY_BACKOFF_SECONDS,
    )
    delay = max(declared, backoff) + random.uniform(0, backoff / 2)
    remaining = deadline - time.monotonic()
    return delay if delay < remaining else None


def _retry_after_seconds(error: Exception) -> float:
    headers = getattr(getattr(error, "response", None), "headers", {}) or {}
    retry_after = headers.get("retry-after") if hasattr(headers, "get") else None
    try:
        return float(retry_after) if retry_after else 0.0
    except (TypeError, ValueError):
        return 0.0


def _is_retryable(error: Exception) -> bool:
    if isinstance(error, RateLimitError):
        # Cota diária esgotada não se resolve com retry: cada tentativa
        # consume mais cota e atrasa a execução. Só repetimos 429 com
        # Retry-After explícito e curto, sinal de limite momentâneo.
        return 0 < _retry_after_seconds(error) <= MAX_RETRY_AFTER_SECONDS
    if isinstance(error, (APIConnectionError, APITimeoutError)):
        return True
    if isinstance(error, APIStatusError):
        if error.status_code == 429:
            return 0 < _retry_after_seconds(error) <= MAX_RETRY_AFTER_SECONDS
        return error.status_code in RETRYABLE_STATUS_CODES
    return isinstance(error, (TimeoutError, ConnectionError))


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
            raise ProviderTimeoutFailure("LLM excedeu o tempo máximo da execução.")
        try:
            request_options = {"max_tokens": max_tokens} if max_tokens else {}
            request_client = llm_client.with_options(timeout=remaining)
            return request_client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tool_definitions,
                **request_options,
            )
        except Exception as error:
            retryable = _is_retryable(error)
            last_attempt = attempt == MAX_LLM_RETRIES - 1
            if not retryable or last_attempt:
                if isinstance(error, RateLimitError):
                    raise RateLimitFailure(
                        f"LLM continuou limitado após {MAX_LLM_RETRIES} tentativas."
                    ) from error
                if isinstance(error, (APITimeoutError, TimeoutError)):
                    raise ProviderTimeoutFailure(
                        "LLM excedeu o tempo máximo da execução."
                    ) from error
                if isinstance(error, APIStatusError):
                    raise RuntimeError(
                        f"LLM retornou HTTP {error.status_code}."
                    ) from error
                if isinstance(error, APIConnectionError):
                    raise RecoverableExecutionError(
                        "Não foi possível conectar ao LLM."
                    ) from error
                raise
            delay = _retry_delay(error, attempt, deadline)
            if delay is None:
                if isinstance(error, RateLimitError):
                    raise RateLimitFailure(
                        "LLM continuou limitado e o tempo máximo da execução "
                        "foi atingido."
                    ) from error
                raise ProviderTimeoutFailure(
                    "LLM excedeu o tempo máximo da execução."
                ) from error
            time.sleep(delay)
