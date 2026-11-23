import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_secret_env_variants_are_ignored_but_example_is_not():
    secret_result = subprocess.run(
        ["git", "check-ignore", "--no-index", "--quiet", ".env.production"],
        cwd=ROOT,
        check=False,
    )
    example_result = subprocess.run(
        ["git", "check-ignore", "--no-index", "--quiet", ".env.example"],
        cwd=ROOT,
        check=False,
    )

    assert secret_result.returncode == 0
    assert example_result.returncode == 1


def test_env_example_lists_variable_names_without_values():
    lines = (ROOT / ".env.example").read_text(encoding="utf-8").splitlines()
    assignments = [
        line.strip()
        for line in lines
        if line.strip() and not line.lstrip().startswith("#")
    ]

    assert assignments
    for assignment in assignments:
        name, separator, value = assignment.partition("=")
        assert separator
        assert re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name.strip())
        assert value.strip() == ""
