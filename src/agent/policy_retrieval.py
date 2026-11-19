import os
import re
import unicodedata
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Protocol

DEFAULT_EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_COLLECTION_NAME = "clinic_policy_chunks"
DEFAULT_RESULTS_LIMIT = 3
MIN_POLICY_QUERY_COVERAGE = 0.5
_POLICY_QUERY_STOPWORDS = frozenset(
    {
        "a",
        "as",
        "ao",
        "aos",
        "da",
        "das",
        "de",
        "do",
        "dos",
        "e",
        "em",
        "esta",
        "estao",
        "estiver",
        "fazer",
        "foi",
        "na",
        "nas",
        "no",
        "nos",
        "o",
        "os",
        "ou",
        "para",
        "por",
        "qual",
        "quando",
        "que",
        "se",
        "um",
        "uma",
        "umas",
        "uns",
        "voce",
        "voces",
        "paciente",
        "pacientes",
        "clinica",
        "politica",
        "politicas",
    }
)


class PolicyStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVOKED = "revoked"


@dataclass(frozen=True)
class PolicyChunk:
    document_id: str
    version: str
    chunk_id: str
    content: str
    source: str
    status: PolicyStatus
    effective_from: date
    effective_until: date | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    revoked_at: datetime | None = None
    is_test_fixture: bool = False

    def __post_init__(self) -> None:
        for field_name in ("document_id", "version", "chunk_id", "content", "source"):
            if not getattr(self, field_name).strip():
                raise ValueError(f"{field_name} não pode ser vazio.")
        if not isinstance(self.status, PolicyStatus):
            raise ValueError("O estado da política é inválido.")
        if self.effective_until and self.effective_until < self.effective_from:
            raise ValueError("O fim da vigência não pode preceder seu início.")
        if self.status in {PolicyStatus.APPROVED, PolicyStatus.REVOKED} and not (
            self.approved_by and self.approved_by.strip() and self.approved_at
        ):
            raise ValueError(
                "Políticas aprovadas ou revogadas exigem responsável e data de aprovação."
            )
        if self.status == PolicyStatus.REVOKED and not self.revoked_at:
            raise ValueError("Políticas revogadas exigem a data de revogação.")
        if self.status != PolicyStatus.REVOKED and self.revoked_at:
            raise ValueError(
                "A data de revogação só pode existir em políticas revogadas."
            )

    @property
    def index_id(self) -> str:
        return f"{self.document_id}:{self.version}:{self.chunk_id}"


@dataclass(frozen=True)
class PolicySearchResult:
    document_id: str
    version: str
    chunk_id: str
    content: str
    source: str
    effective_from: date
    effective_until: date | None
    distance: float | None
    is_test_fixture: bool


def policy_query_coverage(
    question: str,
    results: list[PolicySearchResult],
) -> float:
    return max(
        policy_query_coverage_by_document(question, results).values(),
        default=0.0,
    )


def policy_query_coverage_by_document(
    question: str,
    results: list[PolicySearchResult],
) -> dict[str, float]:
    query_terms = _policy_terms(question)
    if not query_terms:
        return {}

    terms_by_document: dict[str, set[str]] = {}
    for result in results:
        terms_by_document.setdefault(result.document_id, set()).update(
            _policy_terms(result.content)
        )
    return {
        document_id: len(query_terms & document_terms) / len(query_terms)
        for document_id, document_terms in terms_by_document.items()
    }


def supported_policy_results(
    question: str,
    results: list[PolicySearchResult],
    *,
    minimum_coverage: float = MIN_POLICY_QUERY_COVERAGE,
) -> list[PolicySearchResult]:
    coverage_by_document = policy_query_coverage_by_document(question, results)
    supported_documents = {
        document_id
        for document_id, coverage in coverage_by_document.items()
        if coverage >= minimum_coverage
    }
    return [result for result in results if result.document_id in supported_documents]


def _policy_terms(text: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii").lower()
    terms = set()
    for term in re.findall(r"[a-z0-9]+", ascii_text):
        if term.endswith("s") and len(term) > 4:
            term = term[:-1]
        if term not in _POLICY_QUERY_STOPWORDS and len(term) > 2:
            terms.add(term)
    return terms


class VectorCollection(Protocol):
    def upsert(
        self, *, ids: list[str], documents: list[str], metadatas: list[dict[str, Any]]
    ) -> None: ...

    def query(
        self,
        *,
        query_texts: list[str],
        n_results: int,
        where: dict[str, Any],
        include: list[str],
    ) -> dict[str, Any]: ...


class PolicyRetriever:
    def __init__(self, collection: VectorCollection):
        self._collection = collection

    def upsert(self, chunk: PolicyChunk) -> None:
        self._collection.upsert(
            ids=[chunk.index_id],
            documents=[chunk.content],
            metadatas=[
                {
                    "document_id": chunk.document_id,
                    "version": chunk.version,
                    "chunk_id": chunk.chunk_id,
                    "source": chunk.source,
                    "status": chunk.status.value,
                    "effective_from": chunk.effective_from.isoformat(),
                    "effective_from_ordinal": chunk.effective_from.toordinal(),
                    "effective_until": (
                        chunk.effective_until.isoformat()
                        if chunk.effective_until
                        else ""
                    ),
                    "effective_until_ordinal": (
                        chunk.effective_until.toordinal()
                        if chunk.effective_until
                        else 0
                    ),
                    "approved_by": chunk.approved_by or "",
                    "approved_at": (
                        chunk.approved_at.isoformat() if chunk.approved_at else ""
                    ),
                    "revoked_at": (
                        chunk.revoked_at.isoformat() if chunk.revoked_at else ""
                    ),
                    "is_test_fixture": chunk.is_test_fixture,
                }
            ],
        )

    def search(
        self,
        question: str,
        *,
        as_of: date | None = None,
        limit: int = DEFAULT_RESULTS_LIMIT,
        include_test_fixtures: bool = False,
    ) -> list[PolicySearchResult]:
        if not question.strip():
            raise ValueError("A pergunta de busca não pode ser vazia.")
        if limit < 1:
            raise ValueError("O limite de resultados deve ser positivo.")

        reference_date = as_of or date.today()
        ordinal = reference_date.toordinal()
        response = self._collection.query(
            query_texts=[question],
            n_results=limit,
            where={
                "$and": [
                    {"status": PolicyStatus.APPROVED.value},
                    {"effective_from_ordinal": {"$lte": ordinal}},
                    {
                        "$or": [
                            {"effective_until_ordinal": 0},
                            {"effective_until_ordinal": {"$gte": ordinal}},
                        ]
                    },
                    {"is_test_fixture": include_test_fixtures},
                ]
            },
            include=["documents", "metadatas", "distances"],
        )
        documents = response["documents"][0]
        metadatas = response["metadatas"][0]
        distances = response["distances"][0]
        if len(documents) != len(metadatas) or len(documents) != len(distances):
            raise RuntimeError("O índice retornou resultados vetoriais inconsistentes.")
        return [
            PolicySearchResult(
                document_id=metadata["document_id"],
                version=metadata["version"],
                chunk_id=metadata["chunk_id"],
                content=content,
                source=metadata["source"],
                effective_from=date.fromisoformat(metadata["effective_from"]),
                effective_until=(
                    date.fromisoformat(metadata["effective_until"])
                    if metadata["effective_until"]
                    else None
                ),
                distance=distances[index],
                is_test_fixture=metadata["is_test_fixture"],
            )
            for index, (content, metadata) in enumerate(zip(documents, metadatas))
        ]


def create_policy_retriever(
    persist_directory: str | Path | None = None,
) -> PolicyRetriever:
    import chromadb
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

    configured_directory = (
        str(persist_directory)
        if persist_directory is not None
        else os.getenv("POLICY_INDEX_PATH", "").strip()
    )
    directory = (
        Path(configured_directory)
        if configured_directory
        else (Path.home() / ".cache" / "llm-trabalho" / "policy-index")
    )
    embedding_function = SentenceTransformerEmbeddingFunction(
        model_name=DEFAULT_EMBEDDING_MODEL
    )
    client = chromadb.PersistentClient(path=str(directory))
    collection = client.get_or_create_collection(
        name=DEFAULT_COLLECTION_NAME,
        embedding_function=embedding_function,
        metadata={"hnsw:space": "cosine"},
    )
    return PolicyRetriever(collection)
