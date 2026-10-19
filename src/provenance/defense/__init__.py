"""Prompt injection defense and data sanitation package."""

from provenance.defense.heuristics import InjectionScanResult, scan_text_for_injection
from provenance.defense.classifier import (
    classify_text_llm,
    filter_and_flag_chunks,
    wrap_untrusted_data,
)

__all__ = [
    "scan_text_for_injection",
    "InjectionScanResult",
    "classify_text_llm",
    "filter_and_flag_chunks",
    "wrap_untrusted_data",
]
