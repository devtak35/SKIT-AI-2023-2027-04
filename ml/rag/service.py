"""In-process RAG service facade used by the local app and tests."""

from .retriever import EvidenceRecord, EvidenceRetriever, records_from_extraction

__all__ = ["EvidenceRecord", "EvidenceRetriever", "records_from_extraction"]
