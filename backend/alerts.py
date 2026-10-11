import hashlib
import json
import sqlite3
import uuid
from datetime import datetime, timezone
from backend.config import DATABASE_PATH


# =========================================================
# DATABASE
# =========================================================

# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def get_connection():
    connection = sqlite3.connect(DATABASE_PATH, timeout=10)
    connection.execute("PRAGMA busy_timeout = 10000")

    connection.row_factory = sqlite3.Row

    return connection


def initialize_database():
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = get_connection()

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS alerts (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,

            crop TEXT NOT NULL,
            diagnosis TEXT NOT NULL,
            severity TEXT NOT NULL,
            confidence REAL NOT NULL,

            symptoms TEXT,
            image_filename TEXT,

            status TEXT NOT NULL DEFAULT 'pending',
            priority TEXT NOT NULL DEFAULT 'normal',
            validation_model_version TEXT
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS reports (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            crop TEXT NOT NULL,
            diagnosis TEXT NOT NULL,
            confidence REAL NOT NULL,
            severity TEXT NOT NULL,
            symptoms TEXT NOT NULL,
            prevention_json TEXT NOT NULL,
            expert_review INTEGER NOT NULL,
            alert_id TEXT,
            owner_hash TEXT,
            validation_model_version TEXT,
            result_status TEXT
        )
        """
    )

    report_columns = {row["name"] for row in connection.execute("PRAGMA table_info(reports)").fetchall()}
    if "owner_hash" not in report_columns:
        connection.execute("ALTER TABLE reports ADD COLUMN owner_hash TEXT")
    if "validation_model_version" not in report_columns:
        connection.execute("ALTER TABLE reports ADD COLUMN validation_model_version TEXT")
    if "result_status" not in report_columns:
        connection.execute("ALTER TABLE reports ADD COLUMN result_status TEXT")
    alert_columns = {row["name"] for row in connection.execute("PRAGMA table_info(alerts)").fetchall()}
    if "validation_model_version" not in alert_columns:
        connection.execute("ALTER TABLE alerts ADD COLUMN validation_model_version TEXT")
    connection.commit()
    connection.close()


def _owner_hash(report_key: str) -> str:
    return hashlib.sha256(report_key.encode("utf-8")).hexdigest()


def save_report(report: dict, report_key: str) -> dict:
    """Persist a completed diagnosis without storing the uploaded image."""
    if len(report_key) < 32:
        raise ValueError("A valid report key is required.")
    created_at = datetime.now(timezone.utc).isoformat()
    report_id = report["job_id"]
    connection = get_connection()
    try:
        connection.execute(
            """
            INSERT OR REPLACE INTO reports (
                id, created_at, crop, diagnosis, confidence, severity, symptoms,
                prevention_json, expert_review, alert_id, owner_hash,
                validation_model_version, result_status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                report_id, created_at, report["crop"], report["diagnosis"],
                report["confidence"], report["severity"], report["symptoms"],
                json.dumps(report.get("prevention", [])),
                int(bool(report.get("expert_review"))),
                (report.get("alert") or {}).get("id"),
                _owner_hash(report_key),
                (report.get("validation") or {}).get("model_version"),
                report.get("status"),
            ),
        )
        connection.commit()
    finally:
        connection.close()
    return {**report, "id": report_id, "created_at": created_at}


def link_report_to_alert(report_id: str, alert_id: str) -> None:
    connection = get_connection()
    try:
        cursor = connection.execute(
            "UPDATE reports SET alert_id = ? WHERE id = ?",
            (alert_id, report_id),
        )
        if cursor.rowcount == 0:
            raise ValueError(f"Report {report_id} does not exist.")
        connection.commit()
    finally:
        connection.close()


def get_reports(report_key: str, limit: int = 100) -> list[dict]:
    if len(report_key) < 32:
        raise ValueError("A valid report key is required.")
    connection = get_connection()
    try:
        rows = connection.execute(
            """
            SELECT reports.*, alerts.status AS alert_status
            FROM reports LEFT JOIN alerts ON alerts.id = reports.alert_id
            WHERE reports.owner_hash = ?
            ORDER BY reports.created_at DESC LIMIT ?
            """,
            (_owner_hash(report_key), limit),
        ).fetchall()
    finally:
        connection.close()
    reports = []
    for row in rows:
        validated = bool(row["validation_model_version"])
        reports.append({
            "id": row["id"],
            "created_at": row["created_at"],
            "crop": row["crop"] if validated else None,
            "diagnosis": row["diagnosis"] if validated else None,
            "confidence": row["confidence"] if validated else None,
            "severity": row["severity"] if validated else None,
            "symptoms": row["symptoms"] if validated else "",
            "prevention": json.loads(row["prevention_json"]) if validated else [],
            "expert_review": bool(row["expert_review"]) if validated else True,
            "status": (row["alert_status"] or row["result_status"] or "completed") if validated else "legacy_unvalidated",
            "validation_model_version": row["validation_model_version"],
            "message": None if validated else "This earlier result was generated before crop photo suitability checks were available. Do not treat it as a diagnosis.",
        })
    return reports


# Initialize database when the backend starts
initialize_database()


# =========================================================
# CREATE ALERT
# =========================================================

def create_alert(
    crop: str,
    diagnosis: str,
    severity: str,
    confidence: float,
    symptoms: str,
    image_filename: str | None,
    validation_model_version: str | None = None,
):
    alert_id = str(uuid.uuid4())

    created_at = datetime.now(timezone.utc).isoformat()

    # Determine alert priority
    severity_lower = severity.lower()

    if severity_lower in ["critical", "high"]:
        priority = "high"

    elif severity_lower in ["medium", "moderate"]:
        priority = "medium"

    else:
        priority = "normal"

    connection = get_connection()
    try:
        connection.execute(
            """
            INSERT INTO alerts (
                id, created_at, crop, diagnosis, severity, confidence,
                symptoms, image_filename, status, priority, validation_model_version
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (alert_id, created_at, crop, diagnosis, severity, confidence,
             symptoms, image_filename, "pending", priority, validation_model_version),
        )
        connection.commit()
    finally:
        connection.close()

    return {
        "id": alert_id,
        "created_at": created_at,
        "crop": crop,
        "diagnosis": diagnosis,
        "severity": severity,
        "confidence": confidence,
        "symptoms": symptoms,
        "image_filename": image_filename,
        "validation_model_version": validation_model_version,
        "status": "pending",
        "priority": priority,
    }


# =========================================================
# GET ALL ALERTS
# =========================================================

def get_alerts(status: str | None = None):

    connection = get_connection()

    try:
        if status:
            rows = connection.execute(
                """
                SELECT * FROM alerts WHERE status = ?
                ORDER BY CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
                created_at DESC
                """,
                (status,),
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT * FROM alerts
                ORDER BY CASE priority WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END,
                created_at DESC
                """
            ).fetchall()
    finally:
        connection.close()

    return [dict(row) for row in rows]


# =========================================================
# GET SINGLE ALERT
# =========================================================

def get_alert(alert_id: str):

    connection = get_connection()

    try:
        row = connection.execute("SELECT * FROM alerts WHERE id = ?", (alert_id,)).fetchone()
    finally:
        connection.close()

    if row is None:
        return None

    return dict(row)


# =========================================================
# UPDATE ALERT STATUS
# =========================================================

def update_alert_status(
    alert_id: str,
    status: str,
):

    connection = get_connection()

    try:
        cursor = connection.execute("UPDATE alerts SET status = ? WHERE id = ?", (status, alert_id))
        connection.commit()
        updated = cursor.rowcount > 0
    finally:
        connection.close()

    if not updated:
        return None

    return get_alert(alert_id)
