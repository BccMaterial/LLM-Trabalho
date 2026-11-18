import hashlib

import pytest

from prompts import available_prompts, load_prompt


def test_available_prompts_contains_all_versioned_resources():
    assert available_prompts() == (
        "atendente_v1",
        "gestor_v1",
        "secretaria_v1",
    )


def test_load_prompt_returns_content_and_version_metadata():
    prompt = load_prompt("atendente_v1")

    assert prompt.name == "atendente"
    assert prompt.version == "v1"
    assert prompt.content.startswith("Papel: Atendente administrativo")
    assert prompt.sha256 == hashlib.sha256(prompt.content.encode("utf-8")).hexdigest()


def test_load_prompt_supports_prompts_not_yet_integrated():
    assert load_prompt("gestor_v1").name == "gestor"
    assert load_prompt("secretaria_v1").name == "secretaria"


def test_load_prompt_rejects_unknown_prompt():
    with pytest.raises(ValueError, match="Prompt desconhecido"):
        load_prompt("inexistente_v1")


def test_atendente_prompt_blocks_exposing_appointments():
    prompt = load_prompt("atendente_v1")

    assert "nunca devem ser expostos ao usuário" in prompt.content
    assert "exclusivamente para avaliar disponibilidade" in prompt.content
    assert "Não transcreva nem resuma registros da agenda" in prompt.content
