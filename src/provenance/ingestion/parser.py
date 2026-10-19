"""Document parser for synthetic knowledge base.

Parses Markdown policy documents with YAML front matter into section-level
PolicyChunk objects with stable chunk IDs in the format {doc_id}#{section_id}.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import List, Optional
import yaml

from provenance.models.policy import (
    DocumentMetadata,
    DocumentStatus,
    PolicyChunk,
    PrecedenceLevel,
)

SECTION_HEADER_REGEX = re.compile(
    r"^(#{1,3})\s+(§\d+(?:\.\d+)?)\s*(.*?)$",
    re.MULTILINE,
)

def parse_frontmatter_and_body(text: str) -> tuple[dict, str]:
    """Extract YAML front matter and markdown body from text."""
    parts = text.split("---", 2)
    if len(parts) < 3:
        raise ValueError("Invalid document: missing YAML front matter delimiters (---)")
    raw_frontmatter = parts[1].strip()
    body = parts[2].strip()
    data = yaml.safe_load(raw_frontmatter)
    return data, body

def parse_document_file(file_path: Path) -> tuple[DocumentMetadata, list[PolicyChunk]]:
    """Parse a single markdown file into DocumentMetadata and PolicyChunks."""
    content = file_path.read_text(encoding="utf-8")
    fm_dict, body = parse_frontmatter_and_body(content)

    metadata = DocumentMetadata(
        doc_id=fm_dict["doc_id"],
        title=fm_dict["title"],
        doc_type=fm_dict.get("doc_type", "policy"),
        level=PrecedenceLevel(int(fm_dict["level"])),
        owner=fm_dict.get("owner", "Unknown"),
        department=fm_dict.get("department"),
        region=fm_dict.get("region"),
        legal_entity=fm_dict.get("legal_entity"),
        effective_date=str(fm_dict["effective_date"]),
        expiry_date=str(fm_dict["expiry_date"]) if fm_dict.get("expiry_date") else None,
        status=DocumentStatus(fm_dict.get("status", "active")),
        supersedes=fm_dict.get("supersedes"),
    )

    chunks: list[PolicyChunk] = []

    matches = list(SECTION_HEADER_REGEX.finditer(body))

    if not matches:

        chunk_id = f"{metadata.doc_id}#§1.0"
        chunks.append(
            PolicyChunk(
                chunk_id=chunk_id,
                doc_id=metadata.doc_id,
                section_id="§1.0",
                section_title=metadata.title,
                content=body.strip(),
                metadata=metadata,
            )
        )
        return metadata, chunks

    for i, match in enumerate(matches):
        section_id = match.group(2).strip()
        section_title = match.group(3).strip()
        start_idx = match.end()
        end_idx = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        section_text = body[start_idx:end_idx].strip()

        full_chunk_content = f"{match.group(0).strip()}\n{section_text}".strip()
        chunk_id = f"{metadata.doc_id}#{section_id}"

        chunks.append(
            PolicyChunk(
                chunk_id=chunk_id,
                doc_id=metadata.doc_id,
                section_id=section_id,
                section_title=section_title,
                content=full_chunk_content,
                metadata=metadata,
            )
        )

    return metadata, chunks

def parse_all_documents(kb_dir: Path) -> tuple[list[DocumentMetadata], list[PolicyChunk]]:
    """Parse all markdown documents in the knowledge base directory."""
    all_metadata: list[DocumentMetadata] = []
    all_chunks: list[PolicyChunk] = []

    if not kb_dir.exists():
        raise FileNotFoundError(f"Knowledge base directory does not exist: {kb_dir}")

    for file_path in sorted(kb_dir.glob("*.md")):
        metadata, chunks = parse_document_file(file_path)
        all_metadata.append(metadata)
        all_chunks.extend(chunks)

    return all_metadata, all_chunks
