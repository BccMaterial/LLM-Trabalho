import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

from src.agent.policy_retrieval import (
    MIN_POLICY_QUERY_COVERAGE,
    PolicyChunk,
    PolicyRetriever,
    PolicyStatus,
    policy_query_coverage,
    supported_policy_results,
)

REFERENCE_DATE = date(2026, 11, 18)
RESULTS_LIMITS = (1, 3, 5)
FIXED_CHUNK_SIZE = 96

POLICIES = (
    {
        "document_id": "exam-count",
        "source": "fixture://case/exam-count/v1",
        "content": (
            "Quantidade de exames: um paciente pode realizar de quatro a seis "
            "exames, dependendo do caso. Seis exames não são uma regra universal."
        ),
    },
    {
        "document_id": "referral-origin",
        "source": "fixture://case/referral-origin/v1",
        "content": (
            "Encaminhamento: é necessário um encaminhamento médico. Ele pode "
            "vir de um profissional da própria clínica ou de outra clínica."
        ),
    },
    {
        "document_id": "unavailable-time",
        "source": "fixture://case/unavailable-time/v1",
        "content": (
            "Horário indisponível: informe o paciente e apresente opções reais "
            "retornadas pela agenda ou peça que escolha outra faixa."
        ),
    },
    {
        "document_id": "booking-confirmation",
        "source": "fixture://case/booking-confirmation/v1",
        "content": (
            "Agendamento: grave um horário somente depois da confirmação "
            "explícita do paciente para aquela opção exata."
        ),
    },
)

REVOKED_POLICY = {
    "document_id": "diagnosis-deadline-revoked",
    "source": "fixture://case/diagnosis-deadline/revoked-v1",
    "content": "Prazo de diagnóstico: a clínica garante o resultado em 30 dias.",
}

QUESTIONS = (
    {
        "id": 1,
        "question": "Quantos exames um paciente pode realizar?",
        "route": "rag",
        "expected_document": "exam-count",
    },
    {
        "id": 2,
        "question": "Um encaminhamento de outra clínica é aceito?",
        "route": "rag",
        "expected_document": "referral-origin",
    },
    {
        "id": 3,
        "question": "O que fazer se o horário escolhido estiver indisponível?",
        "route": "rag",
        "expected_document": "unavailable-time",
    },
    {
        "id": 4,
        "question": "Todo paciente precisa realizar exatamente seis exames?",
        "route": "rag",
        "expected_document": "exam-count",
    },
    {
        "id": 5,
        "question": "Quais exames estão marcados para mim?",
        "route": "api",
        "expected_document": None,
    },
    {
        "id": 6,
        "question": "Meu encaminhamento foi registrado?",
        "route": "api",
        "expected_document": None,
    },
    {
        "id": 7,
        "question": "Quais horários estão disponíveis para meu agendamento?",
        "route": "api",
        "expected_document": None,
    },
    {
        "id": 8,
        "question": "Qual é a minha posição ou situação na fila?",
        "route": "api",
        "expected_document": None,
    },
    {
        "id": 9,
        "question": "Quem aprovou a política de encaminhamentos vigente?",
        "route": "api",
        "expected_document": None,
    },
    {
        "id": 10,
        "question": "Qual prazo de diagnóstico a clínica garante?",
        "route": "rag",
        "expected_document": None,
    },
)


def _chunk(
    document: dict[str, str],
    chunk_id: str,
    content: str,
    *,
    status: PolicyStatus = PolicyStatus.APPROVED,
    revoked_at: datetime | None = None,
) -> PolicyChunk:
    return PolicyChunk(
        document_id=document["document_id"],
        version="v1",
        chunk_id=chunk_id,
        content=content,
        source=document["source"],
        status=status,
        effective_from=date(2026, 1, 1),
        approved_by="avaliacao-sintetica",
        approved_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        revoked_at=revoked_at,
        is_test_fixture=True,
    )


def _make_chunks(strategy: str) -> list[PolicyChunk]:
    chunks = []
    for policy in POLICIES:
        if strategy == "structural":
            contents = [("section-1", policy["content"])]
        else:
            contents = [
                (
                    f"fixed-{start // FIXED_CHUNK_SIZE + 1}",
                    policy["content"][start : start + FIXED_CHUNK_SIZE],
                )
                for start in range(0, len(policy["content"]), FIXED_CHUNK_SIZE)
            ]
        chunks.extend(
            _chunk(policy, chunk_id, content) for chunk_id, content in contents
        )
    chunks.append(
        _chunk(
            REVOKED_POLICY,
            "section-1",
            REVOKED_POLICY["content"],
            status=PolicyStatus.REVOKED,
            revoked_at=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
    )
    return chunks


def _new_retriever(embedding_function, strategy: str) -> PolicyRetriever:
    collection = chromadb.EphemeralClient().create_collection(
        name=f"rag-eval-{strategy}-{uuid4().hex}",
        embedding_function=embedding_function,
        metadata={"hnsw:space": "cosine"},
    )
    return PolicyRetriever(collection)


def _evaluate_searches(retriever: PolicyRetriever, strategy: str) -> list[dict]:
    records = []
    for question in QUESTIONS:
        if question["route"] != "rag":
            continue

        for limit in RESULTS_LIMITS:
            results = retriever.search(
                question["question"],
                as_of=REFERENCE_DATE,
                limit=limit,
                include_test_fixtures=True,
            )
            candidates = [
                {
                    "document_id": result.document_id,
                    "source": result.source,
                    "chunk_id": result.chunk_id,
                    "distance": result.distance,
                }
                for result in results
            ]
            coverage = policy_query_coverage(question["question"], results)
            supported_results = supported_policy_results(
                question["question"],
                results,
                minimum_coverage=MIN_POLICY_QUERY_COVERAGE,
            )
            sufficient = bool(supported_results)
            supported_document_ids = {
                result.document_id for result in supported_results
            }
            sources = [
                candidate
                for candidate in candidates
                if candidate["document_id"] in supported_document_ids
            ]
            found_expected = any(
                source["document_id"] == question["expected_document"]
                for source in sources
            )
            no_answer = question["expected_document"] is None
            records.append(
                {
                    "question_id": question["id"],
                    "question": question["question"],
                    "route": question["route"],
                    "chunking": strategy,
                    "retrieval_call": {
                        "limit": limit,
                        "include_test_fixtures": True,
                        "as_of": REFERENCE_DATE.isoformat(),
                    },
                    "candidates": candidates,
                    "sources": sources,
                    "lexical_coverage": coverage,
                    "sufficiency": "suficiente" if sufficient else "insuficiente",
                    "evaluation": (
                        "false_positive"
                        if no_answer and sufficient
                        else (
                            "correct_refusal"
                            if no_answer
                            else "hit" if found_expected else "miss"
                        )
                    ),
                }
            )
    return records


def _structured_question_records() -> list[dict]:
    return [
        {
            "question_id": question["id"],
            "question": question["question"],
            "route": question["route"],
            "retrieval_call": None,
            "sources": [],
            "sufficiency": "not_applicable",
            "evaluation": "not_executed_missing_api_fixture",
        }
        for question in QUESTIONS
        if question["route"] == "api"
    ]


def _summarize(records: list[dict], strategy: str) -> list[dict]:
    summary = []
    for limit in RESULTS_LIMITS:
        searches = [
            record
            for record in records
            if record.get("chunking") == strategy
            and record.get("retrieval_call") is not None
            and record["retrieval_call"]["limit"] == limit
        ]
        answerable = [
            record for record in searches if record["question_id"] in {1, 2, 3, 4}
        ]
        exceptions = [
            record for record in answerable if record["question_id"] in {2, 3, 4}
        ]
        unknown = [record for record in searches if record["question_id"] == 10]
        document_count = sum(
            len({source["document_id"] for source in record["sources"]})
            for record in answerable
        )
        hit_count = sum(record["evaluation"] == "hit" for record in answerable)
        summary.append(
            {
                "chunking": strategy,
                "k": limit,
                "answerable_hits": hit_count,
                "answerable_count": len(answerable),
                "answerable_precision": (
                    hit_count / document_count if document_count else 0.0
                ),
                "exception_hits": sum(
                    record["evaluation"] == "hit" for record in exceptions
                ),
                "exception_count": len(exceptions),
                "unknown_false_positives": sum(
                    record["evaluation"] == "false_positive" for record in unknown
                ),
            }
        )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Avalia a recuperação do corpus RAG.")
    parser.add_argument(
        "--output",
        type=Path,
        help="Arquivo JSON para registrar chamadas, fontes e resultados.",
    )
    arguments = parser.parse_args()

    embedding = SentenceTransformerEmbeddingFunction(
        model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    )
    records = _structured_question_records()
    revoked_checks = []
    summaries = []

    for strategy in ("structural", "fixed"):
        retriever = _new_retriever(embedding, strategy)
        retriever_chunks = _make_chunks(strategy)
        for chunk in retriever_chunks:
            retriever.upsert(chunk)

        strategy_records = _evaluate_searches(retriever, strategy)
        records.extend(strategy_records)
        summaries.extend(_summarize(strategy_records, strategy))

        revoked_results = retriever.search(
            "Qual é o prazo de diagnóstico documentado?",
            as_of=REFERENCE_DATE,
            limit=5,
            include_test_fixtures=True,
        )
        revoked_coverage = policy_query_coverage(
            "Qual é o prazo de diagnóstico documentado?",
            revoked_results,
        )
        supported_revoked_query = supported_policy_results(
            "Qual é o prazo de diagnóstico documentado?",
            revoked_results,
            minimum_coverage=MIN_POLICY_QUERY_COVERAGE,
        )
        revoked_sufficient = bool(supported_revoked_query)
        revoked_sources = [result.source for result in supported_revoked_query]
        revoked_checks.append(
            {
                "question": "Qual é o prazo de diagnóstico documentado?",
                "chunking": strategy,
                "retrieval_call": {
                    "limit": 5,
                    "include_test_fixtures": True,
                    "as_of": REFERENCE_DATE.isoformat(),
                },
                "lexical_coverage": revoked_coverage,
                "sufficiency": ("suficiente" if revoked_sufficient else "insuficiente"),
                "candidates": [result.source for result in revoked_results],
                "revoked_source_returned": any(
                    result.document_id == REVOKED_POLICY["document_id"]
                    for result in revoked_results
                ),
                "returned_sources": revoked_sources,
            }
        )

    report = json.dumps(
        {
            "embedding_model": "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
            "reference_date": REFERENCE_DATE.isoformat(),
            "chunk_size_characters": FIXED_CHUNK_SIZE,
            "minimum_lexical_coverage": MIN_POLICY_QUERY_COVERAGE,
            "records": records,
            "summary": summaries,
            "revoked_policy_checks": revoked_checks,
        },
        ensure_ascii=False,
        indent=2,
    )
    if arguments.output is None:
        print(report)
    else:
        arguments.output.write_text(f"{report}\n", encoding="utf-8")
        print(f"Relatório salvo em {arguments.output}")


if __name__ == "__main__":
    main()
