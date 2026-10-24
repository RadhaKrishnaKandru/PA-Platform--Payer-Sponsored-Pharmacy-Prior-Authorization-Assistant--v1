"""Build a persistent Chroma index from the synthetic policy PDFs."""

import re
from pathlib import Path
from typing import Sequence

from langchain_chroma import Chroma
from langchain_core.documents import Document
from pypdf import PdfReader

from app.config import get_settings
from app.rag.embeddings import get_embeddings

SECTION_HEADINGS = (
    "Overview",
    "Coverage Criteria",
    "Required Documentation",
    "Step Therapy",
    "Quantity Limits",
    "Renewal",
)
_SECTION_NAMES = frozenset(SECTION_HEADINGS)
_HEADER_PATTERN = re.compile(
    r"^Plan:\s*(?P<plan_id>[^|]+)\s*\|\s*"
    r"Drugs:\s*(?P<drugs>[^|]+)\s*\|\s*"
    r"Version:\s*(?P<policy_version>[^|]+)\s*\|\s*"
    r"Effective:\s*(?P<effective_date>.+?)\s*$",
    re.IGNORECASE,
)
_CHUNK_SIZE = 800
_CHUNK_MAX_SIZE = 900
_CHUNK_OVERLAP = 100


def parse_policy_header(header_line: str) -> dict[str, str]:
    """Parse the first-line policy header into Chroma-compatible metadata."""
    match = _HEADER_PATTERN.fullmatch(header_line.strip())
    if match is None:
        raise ValueError("Missing or malformed policy header on page 1.")

    values = {
        key: value.strip()
        for key, value in match.groupdict().items()
    }
    drugs = [drug.strip().casefold() for drug in values["drugs"].split(",")]
    if any(not value for value in values.values()) or not all(drugs):
        raise ValueError("Missing or malformed policy header on page 1.")
    values["drugs"] = "|".join(drugs)
    return values


def split_policy_sections(
    pages: Sequence[str],
) -> list[tuple[int, str, str]]:
    """Split page text by exact section headings while carrying section state."""
    segments: list[tuple[int, str, str]] = []
    current_section: str | None = None

    for page_number, page_text in enumerate(pages, start=1):
        page_sections: dict[str, list[str]] = {}
        lines = page_text.splitlines()
        for line_number, raw_line in enumerate(lines):
            line = raw_line.strip()
            if page_number == 1 and line_number == 0:
                continue
            if line in _SECTION_NAMES:
                current_section = line
                page_sections.setdefault(current_section, [])
            elif current_section and line:
                page_sections.setdefault(current_section, []).append(line)

        for section, lines_in_section in page_sections.items():
            text = "\n".join(lines_in_section).strip()
            if text:
                segments.append((page_number, section, text))

    return segments


def _split_sentences(paragraph: str) -> list[str]:
    """Split a paragraph at sentence-ending whitespace boundaries."""
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", paragraph.strip())
        if sentence.strip()
    ]


def _text_units(text: str) -> list[str]:
    """Keep bullet lists intact and split prose into sentence-sized units."""
    units: list[str] = []
    paragraph_lines: list[str] = []
    bullet_lines: list[str] = []

    def flush_paragraph() -> None:
        if paragraph_lines:
            units.extend(_split_sentences(" ".join(paragraph_lines)))
            paragraph_lines.clear()

    def flush_bullets() -> None:
        if bullet_lines:
            units.append(" ".join(bullet_lines))
            bullet_lines.clear()

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            flush_bullets()
            flush_paragraph()
        elif line.startswith("- "):
            flush_paragraph()
            bullet_lines.append(line)
        elif bullet_lines:
            if bullet_lines[-1].endswith((".", "!", "?")):
                flush_bullets()
                paragraph_lines.append(line)
            else:
                bullet_lines[-1] = f"{bullet_lines[-1]} {line}"
        else:
            paragraph_lines.append(line)

    flush_bullets()
    flush_paragraph()
    return units


def _split_oversized_unit(unit: str) -> list[str]:
    """Split an unusually long sentence at whitespace, never inside a word."""
    words = unit.split()
    pieces: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join((*current, word))
        if current and len(candidate) > _CHUNK_MAX_SIZE:
            pieces.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        pieces.append(" ".join(current))
    return pieces


def _chunk_text(text: str) -> list[str]:
    """Pack sentence and paragraph units into overlapping, word-safe chunks."""
    units = [
        piece
        for unit in _text_units(text)
        for piece in _split_oversized_unit(unit)
    ]
    chunks: list[str] = []
    current: list[str] = []

    for unit in units:
        candidate = " ".join((*current, unit))
        if current and len(candidate) > _CHUNK_SIZE:
            chunks.append(" ".join(current))
            overlap = current[-1]
            current = []
            if (
                len(overlap) <= _CHUNK_OVERLAP
                and len(overlap) + len(unit) + 1 <= _CHUNK_MAX_SIZE
            ):
                current.extend((overlap, unit))
            else:
                current.append(unit)
        else:
            current.append(unit)

    if current:
        chunks.append(" ".join(current))
    return [chunk for chunk in chunks if chunk]


def build_policy_chunks(
    document_name: str, pages: Sequence[str]
) -> list[Document]:
    """Create section-aware documents with complete policy citation metadata."""
    first_line = pages[0].splitlines()[0] if pages and pages[0].splitlines() else ""
    try:
        header = parse_policy_header(first_line)
    except ValueError as exc:
        raise ValueError(f"{document_name}: {exc}") from exc

    chunks: list[Document] = []
    for page, section, text in split_policy_sections(pages):
        for chunk_text in _chunk_text(text):
            chunks.append(
                Document(
                    page_content=f"{section}\n{chunk_text}",
                    metadata={
                        "document": document_name,
                        "page": page,
                        "section": section,
                        "chunk_index": len(chunks),
                        **header,
                    },
                )
            )
    return chunks


def _read_policy(path: Path) -> list[Document]:
    """Read one policy PDF and convert its pages to chunk documents."""
    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return build_policy_chunks(path.name, pages)


def ingest_policies(
    *,
    policies_dir: Path | None = None,
    chroma_dir: Path | None = None,
) -> dict[str, int]:
    """Rebuild the policy collection and return chunk counts by PDF."""
    settings = get_settings()
    policy_path = policies_dir or settings.policies_dir
    persist_path = chroma_dir or settings.chroma_dir
    policy_files = sorted(policy_path.glob("*.pdf"))
    if not policy_files:
        raise FileNotFoundError(f"No policy PDFs found in {policy_path}.")

    documents_by_file = {
        path.name: _read_policy(path)
        for path in policy_files
    }
    embeddings = get_embeddings()
    vector_store = Chroma(
        collection_name=settings.chroma_collection,
        persist_directory=str(persist_path),
        embedding_function=embeddings,
    )
    vector_store.delete_collection()
    vector_store = Chroma(
        collection_name=settings.chroma_collection,
        persist_directory=str(persist_path),
        embedding_function=embeddings,
    )

    documents = [
        document
        for policy_documents in documents_by_file.values()
        for document in policy_documents
    ]
    if documents:
        vector_store.add_documents(documents)

    counts = {
        filename: len(policy_documents)
        for filename, policy_documents in documents_by_file.items()
    }
    for filename, count in counts.items():
        print(f"{filename}: {count} chunks")
    return counts


def main() -> None:
    """Run ingestion as a module and report safe, actionable failures."""
    try:
        ingest_policies()
    except Exception as exc:
        raise SystemExit(f"Policy ingestion failed: {exc}") from exc


if __name__ == "__main__":
    main()
