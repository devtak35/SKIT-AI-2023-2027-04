"""Evidence-backed graph persistence and conservative producer adaptation.

The graph is intentionally a small relational boundary.  It is explainable in
the thesis, works with the existing SQLite fixture, and can be moved behind a
Neo4j adapter later without changing the API or citation contract.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from uuid import uuid4



class GraphValidationError(ValueError):
    """Raised when a producer record cannot be made evidence-backed."""


@dataclass(frozen=True)
class GraphRecord:
    record_id: str
    record_type: str
    session_id: str
    text: str
    status: str
    confidence: float
    evidence: list[dict[str, object]]
    metadata: dict[str, object]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _evidence_refs(raw: object) -> list[dict[str, object]]:
    if not isinstance(raw, list) or not raw:
        raise GraphValidationError("at least one evidence reference is required")
    refs: list[dict[str, object]] = []
    for index, value in enumerate(raw):
        if isinstance(value, str):
            value = {"segment_id": value, "revision": 1}
        if not isinstance(value, dict) or not value.get("segment_id"):
            raise GraphValidationError(f"evidence[{index}] must contain segment_id")
        revision = value.get("revision", 1)
        if not isinstance(revision, int) or revision < 1:
            raise GraphValidationError(f"evidence[{index}].revision must be a positive integer")
        ref = {"segment_id": str(value["segment_id"]), "revision": revision}
        for key in ("start_ms", "end_ms"):
            if value.get(key) is not None:
                if not isinstance(value[key], int) or value[key] < 0:
                    raise GraphValidationError(f"evidence[{index}].{key} must be a non-negative integer")
                ref[key] = value[key]
        if ref.get("start_ms") is not None and ref.get("end_ms") is not None and ref["end_ms"] < ref["start_ms"]:
            raise GraphValidationError(f"evidence[{index}] end_ms precedes start_ms")
        refs.append(ref)
    return refs


class GraphRepository:
    """Store graph records and relationships with immutable evidence links."""

    def __init__(self, connection: sqlite3.Connection | None = None) -> None:
        self._connection = connection or open_configured_database()
        self._lock = Lock()

    @property
    def _postgres(self) -> bool:
        return self._connection.__class__.__module__.startswith("psycopg")

    def _execute(self, query: str, params: tuple = ()):
        return self._connection.execute(query.replace("?", "%s") if self._postgres else query, params)

    def _assert_evidence(self, session_id: str, refs: list[dict[str, object]]) -> None:
        placeholder = "%s" if self._postgres else "?"
        for ref in refs:
            row = self._connection.execute(
                f"SELECT start_ms, end_ms FROM transcript_segments WHERE session_id = {placeholder} AND segment_id = {placeholder} AND revision = {placeholder}",
                (session_id, ref["segment_id"], ref["revision"]),
            ).fetchone()
            if row is None:
                raise GraphValidationError(
                    f"evidence references unknown segment {ref['segment_id']} revision {ref['revision']}"
                )

    def _evidence_exists(self, *, record_type: str, record_id: str, session_id: str,
                         segment_id: str, revision: int) -> bool:
        row = self._execute(
            "SELECT 1 FROM graph_evidence WHERE record_type = ? AND record_id = ? "
            "AND session_id = ? AND segment_id = ? AND segment_revision = ?",
            (record_type, record_id, session_id, segment_id, revision),
        ).fetchone()
        return row is not None

    def ingest(self, *, session_id: str, entities: list[dict], action_items: list[dict], relationships: list[dict], producer: str = "garvit", producer_version: str = "1") -> dict[str, list[dict]]:
        """Normalize and persist one producer batch; reject the whole batch on invalid evidence."""
        now = _now()
        entity_ids: dict[str, str] = {}
        created_entities: list[dict] = []
        created_actions: list[dict] = []
        with self._lock:
            try:
                self._connection.execute("BEGIN") if not self._postgres else None
                for raw in entities:
                    entity_type = raw.get("entity_type", raw.get("type"))
                    if entity_type not in {"person", "topic", "decision"}:
                        raise GraphValidationError("entity type must be person, topic, or decision")
                    name = str(raw.get("display_name", raw.get("text", ""))).strip()
                    if not name:
                        raise GraphValidationError("entity display_name must not be empty")
                    confidence = float(raw.get("confidence", 0))
                    if not 0 <= confidence <= 1:
                        raise GraphValidationError("confidence must be between 0 and 1")
                    refs = _evidence_refs(raw.get("evidence", raw.get("evidence_segment_ids")))
                    self._assert_evidence(session_id, refs)
                    source_id = str(raw.get("id", name))
                    entity_id = str(raw.get("entity_id") or uuid4())
                    entity_ids[source_id] = entity_id
                    entity_ids[entity_id] = entity_id
                    aliases = raw.get("aliases", []) if isinstance(raw.get("aliases", []), list) else []
                    properties = dict(raw.get("properties", {})) if isinstance(raw.get("properties", {}), dict) else {}
                    if entity_type == "decision":
                        properties.setdefault("statement", raw.get("statement", name))
                        properties.setdefault("decision_status", raw.get("decision_status", "proposed"))
                    existing = self._execute(
                        "SELECT entity_type, display_name FROM graph_entities WHERE entity_id = ?",
                        (entity_id,),
                    ).fetchone()
                    if existing is not None:
                        if existing["entity_type"] != entity_type:
                            raise GraphValidationError(
                                f"entity_id {entity_id} is already registered as {existing['entity_type']}"
                            )
                        if existing["display_name"].strip().casefold() != name.casefold():
                            raise GraphValidationError(
                                f"entity_id {entity_id} display_name does not match the canonical entity"
                            )
                    else:
                        self._execute(
                            "INSERT INTO graph_entities(entity_id, origin_session_id, entity_type, display_name, aliases, properties, status, confidence, producer, producer_version, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, ?, ?)",
                            (entity_id, session_id, entity_type, name, json.dumps(aliases), json.dumps(properties), confidence, producer, producer_version, now, now),
                        )
                    for ref in refs:
                        if not self._evidence_exists(record_type="entity", record_id=entity_id, session_id=session_id, segment_id=ref["segment_id"], revision=ref["revision"]):
                            self._execute("INSERT INTO graph_evidence(evidence_id, record_type, record_id, session_id, segment_id, segment_revision, start_ms, end_ms) VALUES (?, 'entity', ?, ?, ?, ?, ?, ?)", (str(uuid4()), entity_id, session_id, ref["segment_id"], ref["revision"], ref.get("start_ms"), ref.get("end_ms")))
                    created_entities.append({"entity_id": entity_id, "entity_type": entity_type, "display_name": name, "evidence": refs})

                for raw in action_items:
                    description = str(raw.get("description", raw.get("text", ""))).strip()
                    if not description:
                        raise GraphValidationError("action item description must not be empty")
                    confidence = float(raw.get("confidence", 0))
                    if not 0 <= confidence <= 1:
                        raise GraphValidationError("confidence must be between 0 and 1")
                    refs = _evidence_refs(raw.get("evidence", raw.get("evidence_segment_ids", raw.get("source_segment_ids"))))
                    self._assert_evidence(session_id, refs)
                    owner_entity_id = raw.get("owner_entity_id")
                    owner_text = str(raw.get("owner", "")).strip()
                    owner_status = raw.get("owner_status") or ("assigned" if owner_entity_id else ("uncertain" if owner_text else "unassigned"))
                    if owner_status == "assigned" and not owner_entity_id:
                        raise GraphValidationError("assigned action item requires owner_entity_id")
                    if owner_entity_id and owner_entity_id in entity_ids:
                        owner_entity_id = entity_ids[owner_entity_id]
                    if owner_entity_id:
                        owner = self._execute("SELECT entity_type FROM graph_entities WHERE entity_id = ?", (owner_entity_id,)).fetchone()
                        if owner is None or owner["entity_type"] != "person":
                            raise GraphValidationError("owner_entity_id must reference a person entity")
                    action_id = str(raw.get("action_item_id") or raw.get("id") or uuid4())
                    properties = dict(raw.get("properties", {})) if isinstance(raw.get("properties", {}), dict) else {}
                    if owner_text and not owner_entity_id:
                        properties["owner_text"] = owner_text
                    if owner_status not in {"assigned", "unassigned", "uncertain"}:
                        raise GraphValidationError("owner_status must be assigned, unassigned, or uncertain")
                    if raw.get("status", "open") not in {"open", "in_progress", "blocked", "completed", "cancelled", "needs_review"}:
                        raise GraphValidationError("unsupported action-item status")
                    related_decision_id = raw.get("related_decision_id")
                    if related_decision_id:
                        related_decision_id = entity_ids.get(str(related_decision_id), str(related_decision_id))
                        decision = self._execute("SELECT entity_type FROM graph_entities WHERE entity_id = ?", (related_decision_id,)).fetchone()
                        if decision is None or decision["entity_type"] != "decision":
                            raise GraphValidationError("related_decision_id must reference a decision entity")
                    self._execute("INSERT INTO graph_action_items(action_item_id, session_id, description, owner_entity_id, owner_status, due_at, due_date_text, status, confidence, related_decision_id, properties, producer, producer_version, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (action_id, session_id, description, owner_entity_id, owner_status, raw.get("due_at"), raw.get("due_date_text", raw.get("due_date")), raw.get("status", "open"), confidence, related_decision_id, json.dumps(properties), producer, producer_version, now, now))
                    for ref in refs:
                        if not self._evidence_exists(record_type="action_item", record_id=action_id, session_id=session_id, segment_id=ref["segment_id"], revision=ref["revision"]):
                            self._execute("INSERT INTO graph_evidence(evidence_id, record_type, record_id, session_id, segment_id, segment_revision, start_ms, end_ms) VALUES (?, 'action_item', ?, ?, ?, ?, ?, ?)", (str(uuid4()), action_id, session_id, ref["segment_id"], ref["revision"], ref.get("start_ms"), ref.get("end_ms")))
                    created_actions.append({"action_item_id": action_id, "description": description, "status": raw.get("status", "open"), "evidence": refs})

                for raw in relationships:
                    source = entity_ids.get(str(raw.get("source_id")), str(raw.get("source_entity_id", "")))
                    target = entity_ids.get(str(raw.get("target_id")), str(raw.get("target_entity_id", "")))
                    if not source or not target or source == target:
                        raise GraphValidationError("relationship endpoints must be distinct known entities")
                    endpoints = self._execute(
                        "SELECT entity_id FROM graph_entities WHERE entity_id IN (?, ?)",
                        (source, target),
                    ).fetchall()
                    if len(endpoints) != 2:
                        raise GraphValidationError("relationship endpoints must reference stored entities")
                    if raw.get("relationship_type") not in {"mentions", "about", "supports", "contradicts", "supersedes", "parent_of", "related_to"}:
                        raise GraphValidationError("unsupported relationship type")
                    relationship_confidence = float(raw.get("confidence", 1))
                    if not 0 <= relationship_confidence <= 1:
                        raise GraphValidationError("relationship confidence must be between 0 and 1")
                    self._execute("INSERT INTO graph_relationships(relationship_id, source_entity_id, relationship_type, target_entity_id, status, confidence, evidence, created_at) VALUES (?, ?, ?, ?, 'active', ?, ?, ?)", (str(raw.get("relationship_id") or uuid4()), source, raw["relationship_type"], target, relationship_confidence, json.dumps(raw.get("evidence", [])), now))
                self._connection.commit() if not self._postgres else None
            except Exception:
                self._connection.rollback()
                raise
        return {"entities": created_entities, "action_items": created_actions}

    def list_session_records(self, session_id: str) -> list[GraphRecord]:
        with self._lock:
            entities = self._execute(
                "SELECT DISTINCT entity.* FROM graph_entities AS entity "
                "LEFT JOIN graph_evidence AS evidence ON evidence.record_type = 'entity' "
                "AND evidence.record_id = entity.entity_id "
                "WHERE entity.status <> 'superseded' AND "
                "(entity.origin_session_id = ? OR evidence.session_id = ?)",
                (session_id, session_id),
            ).fetchall()
            # ``needs_review`` is intentionally returned so clients can show
            # that a source correction invalidated a derived claim.
            actions = self._execute("SELECT * FROM graph_action_items WHERE session_id = ?", (session_id,)).fetchall()
            records: list[GraphRecord] = []
            for row in entities:
                evidence = self._execute("SELECT segment_id, segment_revision, start_ms, end_ms FROM graph_evidence WHERE record_type = 'entity' AND record_id = ? AND session_id = ?", (row["entity_id"], session_id)).fetchall()
                records.append(GraphRecord(row["entity_id"], "entity", session_id, row["display_name"], row["status"], row["confidence"], [dict(item) for item in evidence], json.loads(row["properties"])))
            for row in actions:
                evidence = self._execute("SELECT segment_id, segment_revision, start_ms, end_ms FROM graph_evidence WHERE record_type = 'action_item' AND record_id = ? AND session_id = ?", (row["action_item_id"], session_id)).fetchall()
                metadata = json.loads(row["properties"])
                metadata.update({
                    "owner_entity_id": row["owner_entity_id"],
                    "owner_status": row["owner_status"],
                    "due_at": row["due_at"],
                    "due_date_text": row["due_date_text"],
                    "related_decision_id": row["related_decision_id"],
                })
                records.append(GraphRecord(row["action_item_id"], "action_item", session_id, row["description"], row["status"], row["confidence"], [dict(item) for item in evidence], metadata))
            return records
