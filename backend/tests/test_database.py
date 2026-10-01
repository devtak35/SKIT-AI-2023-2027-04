from backend.app.database import open_fixture_database


def test_initial_schema_supports_session_and_transcript_revision() -> None:
    connection = open_fixture_database()
    connection.execute(
        "INSERT INTO sessions(session_id, title, created_at, updated_at) VALUES (?, ?, ?, ?)",
        ("session-1", "Architecture review", "2026-08-24T09:00:00Z", "2026-08-24T09:00:00Z"),
    )
    connection.execute(
        """
        INSERT INTO transcript_segments
            (segment_id, session_id, revision, is_final, start_ms, end_ms,
             speaker_id, text, asr_confidence, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "segment-1",
            "session-1",
            1,
            0,
            0,
            1200,
            "speaker-1",
            "We will keep the first schema simple.",
            0.98,
            "2026-08-24T09:00:01Z",
        ),
    )
    connection.execute(
        """
        INSERT INTO transcript_segments
            (segment_id, session_id, revision, is_final, start_ms, end_ms,
             speaker_id, text, asr_confidence, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "segment-1",
            "session-1",
            2,
            1,
            0,
            1300,
            "speaker-1",
            "We will keep the initial schema simple.",
            0.99,
            "2026-08-24T09:00:02Z",
        ),
    )
    row = connection.execute(
        "SELECT segment_id, revision, is_final FROM transcript_segments"
    ).fetchall()
    assert [(item["segment_id"], item["revision"], item["is_final"]) for item in row] == [
        ("segment-1", 1, 0),
        ("segment-1", 2, 1),
    ]


def test_schema_rejects_unknown_extraction_type() -> None:
    connection = open_fixture_database()
    connection.execute(
        "INSERT INTO sessions(session_id, created_at, updated_at) VALUES (?, ?, ?)",
        ("session-1", "2026-08-24T09:00:00Z", "2026-08-24T09:00:00Z"),
    )
    try:
        connection.execute(
            """
            INSERT INTO extracted_items
                (item_id, session_id, item_type, text, confidence, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("item-1", "session-1", "unsupported", "bad", 0.5, "now"),
        )
    except Exception as error:
        assert "CHECK constraint failed" in str(error)
    else:
        raise AssertionError("schema accepted an unsupported extraction type")
