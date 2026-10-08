import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path


# =========================================================
# DATABASE
# =========================================================

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = BASE_DIR / "backend" / "alerts.db"


# =========================================================
# DATABASE INITIALIZATION
# =========================================================

def get_connection():
    connection = sqlite3.connect(DATABASE_PATH)

    connection.row_factory = sqlite3.Row

    return connection


def initialize_database():
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
            priority TEXT NOT NULL DEFAULT 'normal'
        )
        """
    )

    connection.commit()
    connection.close()


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
    image_filename: str,
):
    alert_id = str(uuid.uuid4())

    created_at = datetime.now(timezone.utc).isoformat()

    # Determine alert priority
    severity_lower = severity.lower()

    if severity_lower in ["critical", "high"]:
        priority = "high"

    elif severity_lower == "medium":
        priority = "medium"

    else:
        priority = "normal"

    connection = get_connection()

    connection.execute(
        """
        INSERT INTO alerts (
            id,
            created_at,
            crop,
            diagnosis,
            severity,
            confidence,
            symptoms,
            image_filename,
            status,
            priority
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            alert_id,
            created_at,
            crop,
            diagnosis,
            severity,
            confidence,
            symptoms,
            image_filename,
            "pending",
            priority,
        ),
    )

    connection.commit()
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
        "status": "pending",
        "priority": priority,
    }


# =========================================================
# GET ALL ALERTS
# =========================================================

def get_alerts(status: str | None = None):

    connection = get_connection()

    if status:
        rows = connection.execute(
            """
            SELECT *
            FROM alerts
            WHERE status = ?
            ORDER BY
                CASE priority
                    WHEN 'high' THEN 1
                    WHEN 'medium' THEN 2
                    ELSE 3
                END,
                created_at DESC
            """,
            (status,),
        ).fetchall()

    else:
        rows = connection.execute(
            """
            SELECT *
            FROM alerts
            ORDER BY
                CASE priority
                    WHEN 'high' THEN 1
                    WHEN 'medium' THEN 2
                    ELSE 3
                END,
                created_at DESC
            """
        ).fetchall()

    connection.close()

    return [dict(row) for row in rows]


# =========================================================
# GET SINGLE ALERT
# =========================================================

def get_alert(alert_id: str):

    connection = get_connection()

    row = connection.execute(
        """
        SELECT *
        FROM alerts
        WHERE id = ?
        """,
        (alert_id,),
    ).fetchone()

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

    cursor = connection.execute(
        """
        UPDATE alerts
        SET status = ?
        WHERE id = ?
        """,
        (status, alert_id),
    )

    connection.commit()

    updated = cursor.rowcount > 0

    connection.close()

    if not updated:
        return None

    return get_alert(alert_id)
