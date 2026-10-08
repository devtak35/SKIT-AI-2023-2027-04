from ml.rag.retriever import EvidenceRecord, EvidenceRetriever


def test_retrieval_is_session_scoped_and_cites_evidence() -> None:
    retriever = EvidenceRetriever([
        EvidenceRecord("r1", "session-1", "action_item", "Ravi will document the API changes by Monday.", ("seg-2",), 0.98),
        EvidenceRecord("r2", "session-2", "topic", "The API is being reviewed.", ("seg-x",), 0.90),
    ])

    result = retriever.answer("session-1", "Who will document the API?")

    assert result["insufficient_evidence"] is False
    assert result["source_segment_ids"] == ["seg-2"]
    assert len(result["records"]) == 1


def test_retrieval_reports_insufficient_evidence() -> None:
    result = EvidenceRetriever().answer("session-1", "unknown question")
    assert result == {
        "answer": "Insufficient evidence in this session.",
        "insufficient_evidence": True,
        "records": [],
        "source_segment_ids": [],
    }
