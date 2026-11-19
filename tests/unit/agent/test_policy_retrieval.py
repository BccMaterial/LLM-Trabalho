from datetime import date, datetime, timezone
from uuid import uuid4

import chromadb
import pytest
from chromadb.api.types import Documents, Embeddings

from src.agent.policy_retrieval import (
    PolicyChunk,
    PolicyRetriever,
    PolicySearchResult,
    PolicyStatus,
    policy_query_coverage,
    supported_policy_results,
)


class FakeCollection:
    def __init__(self):
        self.records = {}

    def upsert(self, *, ids, documents, metadatas):
        for identifier, document, metadata in zip(ids, documents, metadatas):
            self.records[identifier] = (document, metadata)

    def query(self, *, query_texts, n_results, where, include):
        assert query_texts
        assert "documents" in include
        matching = [
            (document, metadata)
            for document, metadata in self.records.values()
            if _matches(metadata, where)
        ][:n_results]
        return {
            "documents": [[document for document, _ in matching]],
            "metadatas": [[metadata for _, metadata in matching]],
            "distances": [[0.1 for _ in matching]],
        }


class FixtureEmbeddingFunction(chromadb.EmbeddingFunction):
    def __init__(self):
        pass

    def __call__(self, input: Documents) -> Embeddings:
        return [[float(len(text)), float(sum(map(ord, text)) % 127)] for text in input]

    @staticmethod
    def name() -> str:
        return "policy-retrieval-test-fixture"

    @staticmethod
    def build_from_config(config):
        return FixtureEmbeddingFunction()

    def get_config(self):
        return {}


def _matches(metadata, expression):
    if "$and" in expression:
        return all(_matches(metadata, item) for item in expression["$and"])
    if "$or" in expression:
        return any(_matches(metadata, item) for item in expression["$or"])

    key, expected = next(iter(expression.items()))
    actual = metadata[key]
    if isinstance(expected, dict):
        operator, value = next(iter(expected.items()))
        return {
            "$gte": actual >= value,
            "$lte": actual <= value,
        }[operator]
    return actual == expected


def _chunk(
    document_id,
    status,
    *,
    effective_from=date(2026, 1, 1),
    effective_until=None,
    fixture=True,
    revoked_at=None,
):
    return PolicyChunk(
        document_id=document_id,
        version="v1",
        chunk_id="section-1",
        content=f"Synthetic test fixture for {document_id}.",
        source=f"fixture://policies/{document_id}",
        status=status,
        effective_from=effective_from,
        effective_until=effective_until,
        approved_by=(
            "fixture-approver"
            if status in {PolicyStatus.APPROVED, PolicyStatus.REVOKED}
            else None
        ),
        approved_at=(
            datetime(2026, 1, 1, tzinfo=timezone.utc)
            if status in {PolicyStatus.APPROVED, PolicyStatus.REVOKED}
            else None
        ),
        revoked_at=revoked_at,
        is_test_fixture=fixture,
    )


def test_search_returns_only_approved_current_chunks_with_provenance():
    retriever = PolicyRetriever(FakeCollection())
    retriever.upsert(_chunk("current", PolicyStatus.APPROVED))
    retriever.upsert(
        _chunk(
            "pending",
            PolicyStatus.PENDING,
        )
    )
    retriever.upsert(_chunk("rejected", PolicyStatus.REJECTED))
    retriever.upsert(
        _chunk(
            "revoked",
            PolicyStatus.REVOKED,
            revoked_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
    )
    retriever.upsert(
        _chunk(
            "expired",
            PolicyStatus.APPROVED,
            effective_until=date(2026, 3, 31),
        )
    )
    retriever.upsert(
        _chunk(
            "future",
            PolicyStatus.APPROVED,
            effective_from=date(2026, 5, 1),
        )
    )

    results = retriever.search(
        "question about a synthetic policy",
        as_of=date(2026, 4, 15),
        include_test_fixtures=True,
    )

    assert len(results) == 1
    assert results[0].document_id == "current"
    assert results[0].version == "v1"
    assert results[0].source == "fixture://policies/current"
    assert results[0].is_test_fixture is True


def test_search_excludes_synthetic_fixtures_by_default():
    retriever = PolicyRetriever(FakeCollection())
    retriever.upsert(_chunk("fixture", PolicyStatus.APPROVED))

    assert retriever.search("synthetic policy", as_of=date(2026, 4, 15)) == []


def test_chroma_search_filters_approval_and_vigency_metadata():
    client = chromadb.Client()
    collection = client.create_collection(
        name=f"policy_test_{uuid4().hex}",
        embedding_function=FixtureEmbeddingFunction(),
        metadata={"hnsw:space": "cosine"},
    )
    retriever = PolicyRetriever(collection)
    retriever.upsert(_chunk("current", PolicyStatus.APPROVED))
    retriever.upsert(_chunk("pending", PolicyStatus.PENDING))
    retriever.upsert(
        _chunk(
            "revoked",
            PolicyStatus.REVOKED,
            revoked_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )
    )
    retriever.upsert(
        _chunk(
            "expired",
            PolicyStatus.APPROVED,
            effective_until=date(2026, 3, 31),
        )
    )

    results = retriever.search(
        "question about a synthetic policy",
        as_of=date(2026, 4, 15),
        include_test_fixtures=True,
    )

    assert [result.document_id for result in results] == ["current"]
    assert results[0].version == "v1"
    assert results[0].source == "fixture://policies/current"


def test_policy_chunk_requires_approval_metadata_for_approved_state():
    with pytest.raises(ValueError, match="responsável e data de aprovação"):
        PolicyChunk(
            document_id="policy",
            version="v1",
            chunk_id="section-1",
            content="Synthetic test fixture.",
            source="fixture://policies/policy",
            status=PolicyStatus.APPROVED,
            effective_from=date(2026, 1, 1),
            is_test_fixture=True,
        )


def test_policy_chunk_rejects_invalid_effective_range():
    with pytest.raises(ValueError, match="vigência"):
        _chunk(
            "invalid-range",
            PolicyStatus.APPROVED,
            effective_from=date(2026, 5, 1),
            effective_until=date(2026, 4, 1),
        )


def test_policy_query_coverage_accepts_exception_terms_but_rejects_unrelated_terms():
    result = PolicySearchResult(
        document_id="unavailable-time",
        version="v1",
        chunk_id="section-1",
        content=(
            "Horário indisponível: informe o paciente e apresente opções reais "
            "ou peça que escolha outra faixa."
        ),
        source="fixture://policies/unavailable-time",
        effective_from=date(2026, 1, 1),
        effective_until=None,
        distance=0.1,
        is_test_fixture=True,
    )

    assert (
        policy_query_coverage(
            "O que fazer se o horário escolhido estiver indisponível?",
            [result],
        )
        >= 0.5
    )
    assert supported_policy_results(
        "O que fazer se o horário escolhido estiver indisponível?",
        [result],
    ) == [result]
    assert (
        policy_query_coverage(
            "Qual prazo de diagnóstico a clínica garante?",
            [result],
        )
        == 0.0
    )
    assert (
        supported_policy_results(
            "Qual prazo de diagnóstico a clínica garante?",
            [result],
        )
        == []
    )


def test_upsert_preserves_source_version_and_approval_lifecycle_metadata():
    collection = FakeCollection()
    retriever = PolicyRetriever(collection)
    revoked_at = datetime(2026, 3, 1, tzinfo=timezone.utc)
    chunk = _chunk(
        "revoked",
        PolicyStatus.REVOKED,
        revoked_at=revoked_at,
    )

    retriever.upsert(chunk)

    _, metadata = collection.records[chunk.index_id]
    assert metadata["source"] == "fixture://policies/revoked"
    assert metadata["version"] == "v1"
    assert metadata["status"] == "revoked"
    assert metadata["approved_by"] == "fixture-approver"
    assert metadata["approved_at"] == "2026-01-01T00:00:00+00:00"
    assert metadata["revoked_at"] == revoked_at.isoformat()
    assert metadata["effective_from"] == "2026-01-01"


@pytest.mark.parametrize(
    "question,limit",
    [("", 3), ("   ", 3), ("policy", 0), ("policy", -1)],
)
def test_search_rejects_empty_question_or_non_positive_limit(question, limit):
    retriever = PolicyRetriever(FakeCollection())

    with pytest.raises(ValueError):
        retriever.search(question, limit=limit)
