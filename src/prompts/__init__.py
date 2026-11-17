import hashlib
import re
from dataclasses import dataclass
from importlib.resources import files
from typing import Final

_PROMPT_FILES: Final = {
    "atendente_v1": "atendente_v1.txt",
    "gestor_v1": "gestor_v1.txt",
    "secretaria_v1": "secretaria_v1.txt",
}
_PROMPT_NAME_PATTERN = re.compile(r"^(?P<name>.+)_v(?P<version>\d+)$")


@dataclass(frozen=True)
class PromptResource:
    name: str
    version: str
    content: str
    sha256: str


def load_prompt(name: str) -> PromptResource:
    """Carrega um prompt versionado e seus metadados."""
    filename = _PROMPT_FILES.get(name)
    if filename is None:
        raise ValueError(f"Prompt desconhecido: {name}")

    match = _PROMPT_NAME_PATTERN.fullmatch(name)
    if match is None:
        raise ValueError(f"Nome de prompt inválido: {name}")

    content = files(__name__).joinpath(filename).read_text(encoding="utf-8")
    return PromptResource(
        name=match.group("name"),
        version=f"v{match.group('version')}",
        content=content,
        sha256=hashlib.sha256(content.encode("utf-8")).hexdigest(),
    )


def available_prompts() -> tuple[str, ...]:
    """Retorna os identificadores dos prompts versionados disponíveis."""
    return tuple(_PROMPT_FILES)
