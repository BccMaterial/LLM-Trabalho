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
