"""Hybrid retrieval combining BM25, Chroma vector search, and Reciprocal Rank Fusion (RRF)."""

from __future__ import annotations

from typing import Optional
from provenance.config import settings
from provenance.ingestion.indexer import BM25Searcher, VectorSearcher, load_indexes
from provenance.models.policy import PolicyChunk, PrecedenceLevel
from provenance.models.scenario import ScenarioFacts
from provenance.retrieval.authority import is_document_authoritative, matches_scope

class HybridRetriever:
    """Hybrid retriever combining keyword (BM25) and semantic vector search."""

    def __init__(
        self,
        bm25_searcher: BM25Searcher,
        vector_searcher: VectorSearcher,
        chunks: list[PolicyChunk],
        rrf_k: int = 60,
    ):
        self.bm25_searcher = bm25_searcher
        self.vector_searcher = vector_searcher
        self.chunks = chunks
        self.chunks_by_id = {c.chunk_id: c for c in chunks}
        self.rrf_k = rrf_k

    @classmethod
    def from_saved_indexes(cls) -> HybridRetriever:
        """Initialize retriever by loading saved indexes from disk."""
        bm25, vector, chunks = load_indexes()
        return cls(bm25_searcher=bm25, vector_searcher=vector, chunks=chunks)

    def retrieve(
        self,
        query: str,
        facts: Optional[ScenarioFacts] = None,
        top_k: int = 5,
        filter_non_authoritative: bool = True,
    ) -> list[tuple[PolicyChunk, float]]:
        """Retrieve top_k chunks using hybrid search, metadata filtering, and RRF."""
        candidate_pool_size = max(top_k * 4, 20)

        bm25_results = self.bm25_searcher.search(query, top_k=candidate_pool_size)

        vector_results = self.vector_searcher.search(query, top_k=candidate_pool_size)

        rrf_scores: dict[str, float] = {}

        for rank, (chunk, _) in enumerate(bm25_results):
            cid = chunk.chunk_id
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (self.rrf_k + rank + 1))

        for rank, (chunk, _) in enumerate(vector_results):
            cid = chunk.chunk_id
            rrf_scores[cid] = rrf_scores.get(cid, 0.0) + (1.0 / (self.rrf_k + rank + 1))

        scored_candidates: list[tuple[PolicyChunk, float]] = []

        for cid, base_score in rrf_scores.items():
            chunk = self.chunks_by_id.get(cid)
            if not chunk:
                continue

            if filter_non_authoritative and not is_document_authoritative(chunk.metadata):
                continue

            if facts and not matches_scope(chunk.metadata, facts):
                continue

            precedence_bonus = 1.0
            if chunk.metadata.level == PrecedenceLevel.LEVEL_1_UPDATE_EXCEPTION:
                precedence_bonus = 1.30
            elif chunk.metadata.level == PrecedenceLevel.LEVEL_2_REGIONAL_DEPT:
                precedence_bonus = 1.20
            elif chunk.metadata.level == PrecedenceLevel.LEVEL_3_ENTERPRISE:
                precedence_bonus = 1.10
            elif chunk.metadata.level == PrecedenceLevel.LEVEL_4_OPERATIONAL_SOP:
                precedence_bonus = 1.00
            elif chunk.metadata.level == PrecedenceLevel.LEVEL_5_HISTORICAL:
                precedence_bonus = 0.50

            if facts and facts.region and chunk.metadata.region:
                if facts.region.lower() in chunk.metadata.region.lower():
                    precedence_bonus += 0.15

            final_score = base_score * precedence_bonus
            scored_candidates.append((chunk, final_score))

        scored_candidates.sort(key=lambda pair: pair[1], reverse=True)
        return scored_candidates[:top_k]
