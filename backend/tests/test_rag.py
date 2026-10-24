"""Unit and local-index integration tests for policy RAG."""

from pathlib import Path

import pytest
from langchain_core.embeddings import Embeddings

from app.config import Settings
from app.rag import ingest, retriever
from app.rag.embeddings import get_embeddings
from app.rag.ingest import (
    build_policy_chunks,
    ingest_policies,
    parse_policy_header,
    split_policy_sections,
)

BACKEND_DIR = Path(__file__).resolve().parents[1]
POLICIES_DIR = BACKEND_DIR / "data" / "policies"


class DeterministicEmbeddings(Embeddings):
    """Tiny local test embedder that needs no model download."""

    @staticmethod
    def _vector(text: str) -> list[float]:
        variation = sum(ord(character) for character in text) % 997 / 997
        return [1.0, variation, 0.0]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vector(text) for text in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vector(text)


def test_parse_policy_header() -> None:
    parsed = parse_policy_header(
        "Plan: PLAN-A | Drugs: Ozempic, Trulicity | "
        "Version: 2026-01 | Effective: 2026-01-01"
    )

    assert parsed == {
        "plan_id": "PLAN-A",
        "drugs": "ozempic|trulicity",
        "policy_version": "2026-01",
        "effective_date": "2026-01-01",
    }


def test_parse_policy_header_rejects_missing_header() -> None:
    with pytest.raises(ValueError, match="header"):
        parse_policy_header("Policy Overview")


def test_split_policy_sections_carries_section_between_pages() -> None:
    sections = split_policy_sections(
        [
            "Plan: PLAN-A | Drugs: Ozempic | Version: 2026-01 | "
            "Effective: 2026-01-01\n"
            "Overview\nOverview content\n"
            "Required Documentation\nDocumentation on page one",
            "Continued documentation on page two\n"
            "Step Therapy\nStep therapy content",
        ]
    )

    assert sections == [
        (1, "Overview", "Overview content"),
        (1, "Required Documentation", "Documentation on page one"),
        (2, "Required Documentation", "Continued documentation on page two"),
        (2, "Step Therapy", "Step therapy content"),
    ]


def test_chunks_split_on_whole_words_and_keep_checklists_together() -> None:
    checklist = "\n".join(
        [
            "Required Documentation",
            "- Clinical notes documenting the diagnosis.",
            "- HbA1c lab result within the last 90 days.",
            "- List of current and prior medications.",
            "- Prescriber name and NPI.",
        ]
    )
    chunks = build_policy_chunks(
        "sample.pdf",
        [
            "Plan: PLAN-A | Drugs: Ozempic | Version: 2026-01 | "
            "Effective: 2026-01-01\n"
            f"{checklist}",
        ],
    )

    assert len(chunks) == 1
    assert all(
        chunk.page_content.startswith("Required Documentation\n")
        and chunk.page_content[0].isupper()
        for chunk in chunks
    )


def test_long_chunks_break_only_between_words() -> None:
    source = "Clinical " + "supporting " * 180 + "documentation."
    chunks = build_policy_chunks(
        "sample.pdf",
        [
            "Plan: PLAN-A | Drugs: Ozempic | Version: 2026-01 | "
            "Effective: 2026-01-01\n"
            f"Overview\n{source}",
        ],
    )
    source_words = set(source.split()) | {"Overview"}

    assert len(chunks) > 1
    assert all(
        set(chunk.page_content.split()).issubset(source_words)
        for chunk in chunks
    )


def test_policy_chunks_have_complete_metadata_and_section_prefix() -> None:
    chunks = build_policy_chunks(
        "sample.pdf",
        [
            "Plan: PLAN-A | Drugs: Ozempic | Version: 2026-01 | "
            "Effective: 2026-01-01\n"
            "Required Documentation\nSubmit clinical notes.",
        ],
    )

    assert chunks
    assert chunks[0].page_content.startswith("Required Documentation\n")
    assert all(
        {
            "document",
            "page",
            "section",
            "chunk_index",
            "plan_id",
            "drugs",
            "policy_version",
            "effective_date",
        }.issubset(chunk.metadata)
        for chunk in chunks
    )


def test_policy_chunks_fail_clearly_without_header() -> None:
    with pytest.raises(ValueError, match="sample.pdf.*header"):
        build_policy_chunks("sample.pdf", ["Overview\nPolicy text"])


def test_local_chroma_index_and_retrieval_without_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(
        policies_dir=POLICIES_DIR,
        chroma_dir=tmp_path / "chroma",
        chroma_collection="test-policies",
        rag_top_k=3,
        rag_min_score=0.0,
    )
    embeddings = DeterministicEmbeddings()
    monkeypatch.setattr(ingest, "get_settings", lambda: settings)
    monkeypatch.setattr(ingest, "get_embeddings", lambda: embeddings)
    monkeypatch.setattr(retriever, "get_settings", lambda: settings)
    monkeypatch.setattr(retriever, "get_embeddings", lambda: embeddings)

    counts = ingest_policies(
        policies_dir=POLICIES_DIR,
        chroma_dir=settings.chroma_dir,
    )
    expected_documents = {
        "Ozempic": "glp1_policy.pdf",
        "Oxycodone": "opioid_policy.pdf",
        "Humira": "biologic_policy.pdf",
    }
    for drug, expected_document in expected_documents.items():
        chunks = retriever.retrieve_policy_chunks(drug=drug)
        assert chunks
        assert {chunk.metadata["document"] for chunk in chunks} == {
            expected_document
        }
        assert all(
            {"document", "page", "section"}.issubset(chunk.metadata)
            for chunk in chunks
        )

    documentation = retriever.retrieve_policy_chunks(
        drug="Ozempic",
        focus="documentation",
    )
    assert documentation
    assert {
        chunk.metadata["section"] for chunk in documentation
    } == {"Required Documentation"}
    assert retriever.retrieve_policy_chunks(drug="Unknown Medication") == []
    assert set(counts) == {
        "glp1_policy.pdf",
        "opioid_policy.pdf",
        "biologic_policy.pdf",
    }


def test_documentation_retrieval_keeps_checklists_for_every_policy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = Settings(
        policies_dir=POLICIES_DIR,
        chroma_dir=tmp_path / "chroma",
        chroma_collection="documentation-policies",
        rag_top_k=1,
        rag_min_score=0.0,
    )
    embeddings = DeterministicEmbeddings()
    monkeypatch.setattr(ingest, "get_settings", lambda: settings)
    monkeypatch.setattr(ingest, "get_embeddings", lambda: embeddings)
    monkeypatch.setattr(retriever, "get_settings", lambda: settings)
    monkeypatch.setattr(retriever, "get_embeddings", lambda: embeddings)
    ingest_policies(policies_dir=POLICIES_DIR, chroma_dir=settings.chroma_dir)

    checklists = {
        "Ozempic": ("HbA1c", "NPI", "medication"),
        "Oxycodone": ("PDMP", "NPI", "functional assessment"),
        "Humira": ("methotrexate", "tuberculosis", "hepatitis B"),
    }
    for drug, expected_items in checklists.items():
        documents = retriever.retrieve_policy_chunks(
            drug=drug,
            focus="documentation",
        )
        assert documents
        assert {
            document.metadata["section"] for document in documents
        } == {"Required Documentation"}
        text = "\n".join(document.page_content for document in documents)
        assert all(item.casefold() in text.casefold() for item in expected_items)
        assert all(
            document.page_content.startswith(
                f"{document.metadata['section']}\n"
            )
            and document.page_content[0].isupper()
            for document in documents
        )
        chunk_positions = [
            (
                document.metadata["page"],
                document.metadata["chunk_index"],
            )
            for document in documents
        ]
        assert chunk_positions == sorted(chunk_positions)


def test_policy_retrieval_from_real_pdfs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    try:
        get_embeddings()
    except Exception as exc:
        pytest.skip(f"Local embedding model unavailable: {type(exc).__name__}")

    settings = Settings(
        policies_dir=POLICIES_DIR,
        chroma_dir=tmp_path / "chroma",
        chroma_collection="test-policies",
        rag_top_k=3,
    )
    monkeypatch.setattr(retriever, "get_settings", lambda: settings)
    monkeypatch.setattr(ingest, "get_settings", lambda: settings)
    ingest_policies(
        policies_dir=POLICIES_DIR,
        chroma_dir=settings.chroma_dir,
    )

    ozempic = retriever.retrieve_policy_chunks(drug="Ozempic")
    oxycodone = retriever.retrieve_policy_chunks(drug="Oxycodone")
    humira = retriever.retrieve_policy_chunks(drug="Humira")

    assert ozempic and all(
        chunk.metadata["document"] == "glp1_policy.pdf"
        and chunk.metadata["page"] >= 1
        for chunk in ozempic
    )
    assert oxycodone and all(
        chunk.metadata["document"] == "opioid_policy.pdf"
        for chunk in oxycodone
    )
    assert humira and all(
        chunk.metadata["document"] == "biologic_policy.pdf"
        for chunk in humira
    )
    assert retriever.retrieve_policy_chunks(drug="Unknown Medication") == []

    documentation = retriever.retrieve_policy_chunks(
        drug="Ozempic",
        focus="documentation",
    )
    assert documentation
    assert all(
        chunk.metadata["section"] == "Required Documentation"
        for chunk in documentation
    )
    assert all(
        {"document", "page", "section"}.issubset(chunk.metadata)
        for chunk in ozempic + oxycodone + humira + documentation
    )
