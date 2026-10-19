"""SQLite Audit Trail and Reviewer Override Repository.

AGENTS.md Rule: Investigations retain scenario inputs, retrieved evidence,
policy versions, reasoning summary, verdict, and reviewer actions.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from provenance.config import settings
from provenance.models.audit import InvestigationRecord, ReviewerOverride
from provenance.models.decision import Decision, VerdictEnum
from provenance.models.scenario import ScenarioFacts

class AuditRepository:
    """Manages persistent SQLite storage for compliance investigations and overrides."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or settings.db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Create tables if they do not exist."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS investigations (
                    id TEXT PRIMARY KEY,
                    scenario_text TEXT NOT NULL,
                    facts_json TEXT NOT NULL,
                    retrieved_chunks_json TEXT NOT NULL,
                    extracted_rules_json TEXT NOT NULL,
                    verdict TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    decision_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    has_override INTEGER DEFAULT 0,
                    override_verdict TEXT,
                    override_reviewer TEXT,
                    override_justification TEXT,
                    overridden_at TEXT
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS overrides (
                    id TEXT PRIMARY KEY,
                    investigation_id TEXT NOT NULL,
                    original_verdict TEXT NOT NULL,
                    overridden_verdict TEXT NOT NULL,
                    reviewer_name TEXT NOT NULL,
                    justification TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (investigation_id) REFERENCES investigations(id)
                )
                """
            )
            conn.commit()

    def save_investigation(
        self,
        scenario_text: str,
        facts: ScenarioFacts,
        retrieved_chunk_ids: list[str],
        extracted_rule_ids: list[str],
        decision: Decision,
        investigation_id: Optional[str] = None,
    ) -> InvestigationRecord:
        """Persist a new investigation run to the database."""
        inv_id = investigation_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        record = InvestigationRecord(
            id=inv_id,
            scenario_text=scenario_text,
            facts=facts,
            retrieved_chunk_ids=retrieved_chunk_ids,
            extracted_rule_ids=extracted_rule_ids,
            verdict=decision.verdict,
            reason=decision.reason,
            decision=decision,
            created_at=now,
        )

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO investigations (
                    id, scenario_text, facts_json, retrieved_chunks_json,
                    extracted_rules_json, verdict, reason, decision_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.scenario_text,
                    record.facts.model_dump_json(),
                    json.dumps(record.retrieved_chunk_ids),
                    json.dumps(record.extracted_rule_ids),
                    record.verdict.value,
                    record.reason,
                    record.decision.model_dump_json(),
                    record.created_at,
                ),
            )
            conn.commit()

        return record

    def get_investigation(self, investigation_id: str) -> Optional[InvestigationRecord]:
        """Fetch an investigation record by ID."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM investigations WHERE id = ?", (investigation_id,))
            row = cursor.fetchone()
            if not row:
                return None

            return InvestigationRecord(
                id=row["id"],
                scenario_text=row["scenario_text"],
                facts=ScenarioFacts.model_validate_json(row["facts_json"]),
                retrieved_chunk_ids=json.loads(row["retrieved_chunks_json"]),
                extracted_rule_ids=json.loads(row["extracted_rules_json"]),
                verdict=VerdictEnum(row["verdict"]),
                reason=row["reason"],
                decision=Decision.model_validate_json(row["decision_json"]),
                created_at=row["created_at"],
                has_override=bool(row["has_override"]),
                override_verdict=VerdictEnum(row["override_verdict"]) if row["override_verdict"] else None,
                override_reviewer=row["override_reviewer"],
                override_justification=row["override_justification"],
            )

    def list_investigations(self, limit: int = 50) -> list[InvestigationRecord]:
        """List recent investigations ordered by timestamp descending."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM investigations ORDER BY created_at DESC LIMIT ?",
                (limit,),
            )
            rows = cursor.fetchall()
            records: list[InvestigationRecord] = []
            for row in rows:
                records.append(
                    InvestigationRecord(
                        id=row["id"],
                        scenario_text=row["scenario_text"],
                        facts=ScenarioFacts.model_validate_json(row["facts_json"]),
                        retrieved_chunk_ids=json.loads(row["retrieved_chunks_json"]),
                        extracted_rule_ids=json.loads(row["extracted_rules_json"]),
                        verdict=VerdictEnum(row["verdict"]),
                        reason=row["reason"],
                        decision=Decision.model_validate_json(row["decision_json"]),
                        created_at=row["created_at"],
                        has_override=bool(row["has_override"]),
                        override_verdict=VerdictEnum(row["override_verdict"]) if row["override_verdict"] else None,
                        override_reviewer=row["override_reviewer"],
                        override_justification=row["override_justification"],
                    )
                )
            return records

    def record_override(self, override: ReviewerOverride) -> InvestigationRecord:
        """Record a human reviewer override for an investigation."""
        now = datetime.now(timezone.utc).isoformat()
        override_id = str(uuid.uuid4())

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO overrides (
                    id, investigation_id, original_verdict, overridden_verdict,
                    reviewer_name, justification, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    override_id,
                    override.investigation_id,
                    override.original_verdict.value,
                    override.overridden_verdict.value,
                    override.reviewer_name,
                    override.justification,
                    now,
                ),
            )
            cursor.execute(
                """
                UPDATE investigations SET
                    has_override = 1,
                    override_verdict = ?,
                    override_reviewer = ?,
                    override_justification = ?,
                    overridden_at = ?
                WHERE id = ?
                """,
                (
                    override.overridden_verdict.value,
                    override.reviewer_name,
                    override.justification,
                    now,
                    override.investigation_id,
                ),
            )
            conn.commit()

        updated = self.get_investigation(override.investigation_id)
        if not updated:
            raise ValueError(f"Investigation {override.investigation_id} not found")
        return updated
