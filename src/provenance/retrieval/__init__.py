"""Retrieval and authority package for Provenance."""

from provenance.retrieval.authority import (
    is_date_valid,
    is_document_authoritative,
    matches_scope,
)
from provenance.retrieval.hybrid import HybridRetriever

__all__ = [
    "is_document_authoritative",
    "is_date_valid",
    "matches_scope",
    "HybridRetriever",
]
