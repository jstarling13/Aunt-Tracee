# =============================================================================
# sync_tracker.py — SQLite-backed log of every sync attempt (all 13 stores)
# =============================================================================
# One row per sync attempt, per store, per week. Full audit trail — no deletes.
# Schema includes week_start/week_end so we track weekly syncs correctly.
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
                sync_timestamp   TEXT NOT NULL,   -- ISO datetime when sync ran
                location_id      TEXT NOT NULL,   -- Crunchtime location ID
                store_name       TEXT NOT NULL,   -- human-readable store name
                week_start       TEXT NOT NULL,   -- YYYY-MM-DD (Sunday)
                week_end         TEXT NOT NULL,   -- YYYY-MM-DD (Saturday)
                status           TEXT NOT NULL,   -- pending | success | failed
                error_message    TEXT,            -- NULL on success
                qbxml_sent       TEXT,            -- full XML sent to QB
                qb_response      TEXT,            -- full XML response from QB
                retry_count      INTEGER DEFAULT 0
            )
        ''')
        conn.commit()
    logger.info("Sync tracker database ready: %s", config.SYNC_DB_PATH)


def record_attempt(
    location_id:   str,
    store_name:    str,
    week_start:    date,
    week_end:      date,
    status:        str,
    qbxml_sent:    str = None,
    qb_response:   str = None,
    error_message: str = None,
) -> int:
    """
    Insert a new sync attempt row and return its row ID.
    Called at the start of each store's weekly sync.
    """
    with _get_connection() as conn:
        cursor = conn.execute(
            '''
            INSERT INTO sync_log
                (sync_timestamp, location_id, store_name, week_start, week_end,
                 status, error_message, qbxml_sent, qb_response)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''',
            (
                datetime.utcnow().isoformat(),
                location_id,
                store_name,
                week_start.isoformat(),
                week_end.isoformat(),
                status,
                error_message,
                qbxml_sent,
                qb_response,
            )
        )
        conn.commit()
    row_id = cursor.lastrowid
    logger.info("Sync attempt recorded: id=%s store=%s week=%s status=%s",
                row_id, store_name, week_start, status)
    return row_id


def update_attempt(row_id: int, status: str,
                   qb_response: str = None, error_message: str = None):
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


def already_synced(location_id: str, week_start: date) -> bool:
    """
    Return True if a successful sync already exists for this store + week.
    Prevents duplicate journal entries in QuickBooks.
    """
    with _get_connection() as conn:
        row = conn.execute(
            '''
            SELECT id FROM sync_log
             WHERE location_id = ?
               AND week_start  = ?
               AND status      = 'success'
             LIMIT 1
            ''',
            (location_id, week_start.isoformat())
        ).fetchone()
    if row:
        logger.warning("Store %s week %s already synced (id=%s) — skipping.",
                       location_id, week_start, row['id'])
        return True
    return False


def get_failed_syncs() -> list:
    """Return all failed sync attempts that haven't exceeded retry limit."""
    with _get_connection() as conn:
        rows = conn.execute(
            '''
            SELECT * FROM sync_log
             WHERE status = 'failed'
               AND retry_count < ?
             ORDER BY id ASC
            ''',
            (config.MAX_RETRY_ATTEMPTS,)
        ).fetchall()
    return [dict(r) for r in rows]


def increment_retry(row_id: int):
    """Increment the retry counter for a failed sync attempt."""
    with _get_connection() as conn:
        conn.execute(
            'UPDATE sync_log SET retry_count = retry_count + 1 WHERE id = ?',
            (row_id,)
        )
        conn.commit()


def get_recent_syncs(limit: int = 50) -> list:
    """Return the most recent sync attempts across all stores."""
    with _get_connection() as conn:
        rows = conn.execute(
            'SELECT * FROM sync_log ORDER BY id DESC LIMIT ?', (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_store_status() -> list:
    """
    Return the latest sync status for each store.
    Used by the dashboard to show a per-store health summary.
    """
    with _get_connection() as conn:
        rows = conn.execute(
            '''
            SELECT s.*
            FROM sync_log s
            INNER JOIN (
                SELECT location_id, MAX(id) as max_id
                FROM sync_log
                GROUP BY location_id
            ) latest ON s.id = latest.max_id
            ORDER BY s.store_name ASC
            '''
        ).fetchall()
    return [dict(r) for r in rows]
