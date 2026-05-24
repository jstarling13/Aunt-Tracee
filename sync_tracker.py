# =============================================================================
# sync_tracker.py — SQLite-backed log of every sync attempt
# =============================================================================
# Creates sync_tracker.db automatically on first run.
# Schema: one row per sync attempt. Never deletes rows — full audit trail.
# =============================================================================

import sqlite3
import logging
from datetime import datetime, date

import config

logger = logging.getLogger(__name__)


def _get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(config.SYNC_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def initialize_db():
    """Create the sync_log table if it does not already exist."""
    with _get_connection() as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS sync_log (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                sync_timestamp   TEXT NOT NULL,          -- ISO datetime when sync ran
                business_date    TEXT NOT NULL,          -- YYYY-MM-DD sales date
                location_id      TEXT NOT NULL,          -- Crunchtime location ID
                status           TEXT NOT NULL,          -- success | failed | pending
                error_message    TEXT,                   -- NULL on success
                qbxml_sent       TEXT,                   -- full XML payload sent to QB
                qb_response      TEXT                    -- full XML response from QB
            )
        ''')
        conn.commit()
    logger.info("Sync tracker database ready: %s", config.SYNC_DB_PATH)


def record_attempt(
    business_date: date,
    status: str,
    qbxml_sent: str = None,
    qb_response: str = None,
    error_message: str = None,
) -> int:
    """
    Insert a new sync attempt row and return its row ID.

    Args:
        business_date: the sales date being synced
        status:        'pending' | 'success' | 'failed'
        qbxml_sent:    the XML string sent to QuickBooks
        qb_response:   the XML string received from QuickBooks
        error_message: human-readable error description on failure

    Returns:
        int: the new row's primary key (useful for update_attempt)
    """
    with _get_connection() as conn:
        cursor = conn.execute(
            '''
            INSERT INTO sync_log
                (sync_timestamp, business_date, location_id, status, error_message, qbxml_sent, qb_response)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                datetime.utcnow().isoformat(),
                business_date.isoformat(),
                config.CRUNCHTIME_LOCATION_ID,
                status,
                error_message,
                qbxml_sent,
                qb_response,
            )
        )
        conn.commit()
    row_id = cursor.lastrowid
    logger.info("Sync attempt recorded: id=%s date=%s status=%s", row_id, business_date, status)
    return row_id


def update_attempt(row_id: int, status: str, qb_response: str = None, error_message: str = None):
    """Update the status/response of an existing sync attempt row."""
    with _get_connection() as conn:
        conn.execute(
            '''
            UPDATE sync_log
               SET status        = ?,
                   qb_response   = ?,
                   error_message = ?
             WHERE id = ?
            ''',
            (status, qb_response, error_message, row_id)
        )
        conn.commit()
    logger.info("Sync attempt updated: id=%s new_status=%s", row_id, status)


def already_synced(business_date: date) -> bool:
    """
    Return True if a successful sync already exists for this date + location.
    Prevents posting duplicate journal entries to QuickBooks.
    """
    with _get_connection() as conn:
        row = conn.execute(
            '''
            SELECT id FROM sync_log
             WHERE business_date = ?
               AND location_id   = ?
               AND status        = 'success'
             LIMIT 1
            ''',
            (business_date.isoformat(), config.CRUNCHTIME_LOCATION_ID)
        ).fetchone()
    if row:
        logger.warning(
            "Date %s already successfully synced (row id=%s) — skipping.", business_date, row['id']
        )
        return True
    return False


def get_recent_syncs(limit: int = 20) -> list:
    """Return the most recent sync attempts as a list of dicts (for debugging)."""
    with _get_connection() as conn:
        rows = conn.execute(
            'SELECT * FROM sync_log ORDER BY id DESC LIMIT ?', (limit,)
        ).fetchall()
    return [dict(r) for r in rows]
