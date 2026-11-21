"""Compatibilidade: a implementação agora vive em ``src/judge/validate.py``."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.judge.rubric import (  # noqa: E402
    DECISOES,
    JUDGE_MAX_TOKENS,
    JUDGE_TEMPERATURE,
    PROMPT_PATH,
    RUNS_DIR,
    VALIDATION_PATH,
    build_decision,
    build_prompt,
    compute_matrix,
    normalizar_decisao,
    parse_judge_response,
    read_json,
    sha256,
    verify_pre_registration,
    write_json,
)
from src.judge.validate import (  # noqa: E402
    apply_run,
    call_judge,
    dry_run,
    main,
)

__all__ = [
    "DECISOES",
    "JUDGE_MAX_TOKENS",
    "JUDGE_TEMPERATURE",
    "PROMPT_PATH",
    "RUNS_DIR",
    "VALIDATION_PATH",
    "apply_run",
    "build_decision",
    "build_prompt",
    "call_judge",
    "compute_matrix",
    "dry_run",
    "main",
    "normalizar_decisao",
    "parse_judge_response",
    "read_json",
    "sha256",
    "verify_pre_registration",
    "write_json",
]

if __name__ == "__main__":
    main()
