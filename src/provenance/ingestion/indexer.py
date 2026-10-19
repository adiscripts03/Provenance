"""Index builder and storage for BM25 and Vector search."""

from __future__ import annotations

import pickle
import re
from pathlib import Path
from typing import Any, List, Optional, Tuple

import chromadb
from chromadb.api.models.Collection import Collection
from rank_bm25 import BM25Okapi
from sentence_transformers import SentenceTransformer

from provenance.config import settings
from provenance.ingestion.parser import parse_all_documents
from provenance.models.policy import PolicyChunk

TOKEN_PATTERN = re.compile(r"\w+")

def tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase alphanumeric tokens."""
    return [match.group(0).lower() for match in TOKEN_PATTERN.finditer(text)]

class BM25Searcher:
    """Wrapper for BM25 Okapi index over policy chunks."""

    def __init__(self, bm25: BM25Okapi, chunks: list[PolicyChunk]):
        self.bm25 = bm25
        self.chunks = chunks

    def search(self, query: str, top_k: int = 10) -> list[tuple[PolicyChunk, float]]:
        """Return top_k (chunk, score) pairs matching the query."""
        tokenized_query = tokenize(query)
        if not tokenized_query:
            return []
        scores = self.bm25.get_scores(tokenized_query)
        scored_pairs = list(zip(self.chunks, scores))
        scored_pairs.sort(key=lambda pair: pair[1], reverse=True)
        return scored_pairs[:top_k]

    def save(self, file_path: Path) -> None:
        """Persist BM25 index and chunk list to disk."""
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "wb") as f:
            pickle.dump({"bm25": self.bm25, "chunks": self.chunks}, f)

    @classmethod
    def load(cls, file_path: Path) -> BM25Searcher:
        """Load BM25 index and chunks from disk."""
        with open(file_path, "rb") as f:
            data = pickle.load(f)
        return cls(bm25=data["bm25"], chunks=data["chunks"])

class VectorSearcher:
    """Wrapper for Chroma vector collection with local SentenceTransformer embeddings."""

    def __init__(
        self,
        collection: Collection,
        chunks_by_id: dict[str, PolicyChunk],
        embedding_model: SentenceTransformer,
    ):
        self.collection = collection
        self.chunks_by_id = chunks_by_id
        self.embedding_model = embedding_model

    def search(
        self,
        query: str,
        top_k: int = 10,
        where_filter: Optional[dict[str, Any]] = None,
    ) -> list[tuple[PolicyChunk, float]]:
        """Perform semantic vector similarity search against Chroma."""
        query_embedding = self.embedding_model.encode([query], normalize_embeddings=True).tolist()[0]
        kwargs: dict[str, Any] = {
            "query_embeddings": [query_embedding],
            "n_results": min(top_k, max(1, self.collection.count())),
        }
        if where_filter:
            kwargs["where"] = where_filter

        results = self.collection.query(**kwargs)
        matched_chunks: list[tuple[PolicyChunk, float]] = []

        ids = results.get("ids", [[]])[0]
        distances = results.get("distances", [[]])[0] if "distances" in results else [0.0] * len(ids)

        for chunk_id, dist in zip(ids, distances):
            if chunk_id in self.chunks_by_id:

                similarity = 1.0 - (dist if dist is not None else 0.0)
                matched_chunks.append((self.chunks_by_id[chunk_id], similarity))

        return matched_chunks

def build_and_save_indexes(
    kb_dir: Optional[Path] = None,
    indexes_dir: Optional[Path] = None,
    embedding_model_name: Optional[str] = None,
) -> tuple[BM25Searcher, VectorSearcher, list[PolicyChunk]]:
    """Parse knowledge base and generate both BM25 and Chroma vector indexes."""
    kb_path = kb_dir or settings.kb_dir
    idx_path = indexes_dir or settings.indexes_dir
    model_name = embedding_model_name or settings.embedding_model

    idx_path.mkdir(parents=True, exist_ok=True)

    print(f"Parsing knowledge base documents from {kb_path}...")
    _, chunks = parse_all_documents(kb_path)
    print(f"Extracted {len(chunks)} policy section chunks.")

    print("Building BM25 index...")
    corpus = [tokenize(c.content) for c in chunks]
    bm25 = BM25Okapi(corpus)
    bm25_searcher = BM25Searcher(bm25, chunks)
    bm25_searcher.save(idx_path / "bm25.pkl")
    print(f"Saved BM25 index to {idx_path / 'bm25.pkl'}")

    print(f"Loading embedding model '{model_name}'...")
    embedder = SentenceTransformer(model_name)

    chroma_dir = idx_path / "chroma"
    chroma_client = chromadb.PersistentClient(path=str(chroma_dir))

    try:
        chroma_client.delete_collection(name="provenance_policies")
    except Exception:
        pass

    collection = chroma_client.create_collection(
        name="provenance_policies",
        metadata={"hnsw:space": "cosine"},
    )

    ids = [c.chunk_id for c in chunks]
    documents = [c.content for c in chunks]
    metadatas = [
        {
            "doc_id": c.doc_id,
            "section_id": c.section_id,
            "level": int(c.metadata.level),
            "status": str(c.metadata.status.value),
            "department": c.metadata.department or "",
            "region": c.metadata.region or "",
            "legal_entity": c.metadata.legal_entity or "",
            "effective_date": c.metadata.effective_date,
            "expiry_date": c.metadata.expiry_date or "",
            "supersedes": c.metadata.supersedes or "",
        }
        for c in chunks
    ]

    print("Computing embeddings and indexing into Chroma...")
    embeddings = embedder.encode(documents, normalize_embeddings=True, show_progress_bar=False).tolist()

    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas,
    )
    print(f"Added {len(ids)} chunks to Chroma collection at {chroma_dir}")

    with open(idx_path / "chunks.pkl", "wb") as f:
        pickle.dump(chunks, f)

    chunks_by_id = {c.chunk_id: c for c in chunks}
    vector_searcher = VectorSearcher(collection, chunks_by_id, embedder)

    return bm25_searcher, vector_searcher, chunks

def load_indexes(
    indexes_dir: Optional[Path] = None,
    embedding_model_name: Optional[str] = None,
) -> tuple[BM25Searcher, VectorSearcher, list[PolicyChunk]]:
    """Load existing indexes from disk."""
    idx_path = indexes_dir or settings.indexes_dir
    model_name = embedding_model_name or settings.embedding_model

    if not (idx_path / "bm25.pkl").exists() or not (idx_path / "chunks.pkl").exists():
        return build_and_save_indexes(indexes_dir=idx_path, embedding_model_name=model_name)

    bm25_searcher = BM25Searcher.load(idx_path / "bm25.pkl")

    with open(idx_path / "chunks.pkl", "rb") as f:
        chunks: list[PolicyChunk] = pickle.load(f)
    chunks_by_id = {c.chunk_id: c for c in chunks}

    chroma_dir = idx_path / "chroma"
    chroma_client = chromadb.PersistentClient(path=str(chroma_dir))
    collection = chroma_client.get_collection(name="provenance_policies")
    embedder = SentenceTransformer(model_name)
    vector_searcher = VectorSearcher(collection, chunks_by_id, embedder)

    return bm25_searcher, vector_searcher, chunks
