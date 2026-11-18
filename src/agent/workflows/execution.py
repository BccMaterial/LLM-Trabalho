from datetime import datetime, timedelta, timezone
from enum import Enum

MAX_WORKFLOW_STEPS = 8
MAX_EXTERNAL_CALLS = 10
MAX_MODEL_TOKENS = 6000
MAX_EXECUTION_SECONDS = 120
MAX_COMPLETION_TOKENS_PER_CALL = 1000
MAX_IDENTICAL_TOOL_CALLS = 1
MAX_EXTERNAL_CALL_SECONDS = 30
APPROVAL_TTL_SECONDS = 120
LANGGRAPH_RECURSION_LIMIT = 32


class TerminationReason(str, Enum):
    NORMAL_COMPLETION = "normal_completion"
    USER_EXIT = "user_exit"
    LIMIT_REACHED = "limit_reached"
    ACTION_REJECTED = "action_rejected"
    APPROVAL_EXPIRED = "approval_expired"
    UNPRODUCTIVE_LOOP = "unproductive_loop"
    RECOVERABLE_ERROR = "recoverable_error"
    FATAL_ERROR = "fatal_error"


class ErrorClass(str, Enum):
    RECOVERABLE = "recoverable"
    FATAL = "fatal"


class FatalExecutionError(Exception):
    pass


def classify_execution_error(error: Exception) -> ErrorClass:
    if isinstance(error, FatalExecutionError):
        return ErrorClass.FATAL
    if isinstance(error, (RuntimeError, TimeoutError, ConnectionError)):
        return ErrorClass.RECOVERABLE
    return ErrorClass.FATAL


def new_execution_deadline() -> str:
    return (
        datetime.now(timezone.utc) + timedelta(seconds=MAX_EXECUTION_SECONDS)
    ).isoformat()


def new_approval_deadline() -> str:
    return (
        datetime.now(timezone.utc) + timedelta(seconds=APPROVAL_TTL_SECONDS)
    ).isoformat()


def remaining_seconds(deadline: str | None) -> float:
    if deadline is None:
        return float(MAX_EXTERNAL_CALL_SECONDS)
    remaining = (
        datetime.fromisoformat(deadline) - datetime.now(timezone.utc)
    ).total_seconds()
    return max(0.0, min(float(MAX_EXTERNAL_CALL_SECONDS), remaining))


def deadline_expired(deadline: str | None) -> bool:
    if deadline is None:
        return False
    return datetime.fromisoformat(deadline) <= datetime.now(timezone.utc)
