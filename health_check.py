# =============================================================================
# health_check.py — Full system health report
# =============================================================================
# Checks every component and prints a pass/fail status for each.
# Safe to run at any time — read-only, no data is modified.
#
# Run: python main.py health
# =============================================================================

import sqlite3
import os
import logging
from datetime import datetime, timedelta, date

import requests

import config
import sync_tracker

logger = logging.getLogger(__name__)


def run() -> bool:
    """
    Execute all health checks and print a status report.
    Returns True if everything passes, False if any check fails.
    """
    print()
    print("=" * 60)
    print("  SYSTEM HEALTH CHECK")
    print(f"  {datetime.now().strftime('%Y-%m-%d %I:%M %p')}")
    print("=" * 60)
    print()

    checks = [
        ("Config — no PLACEHOLDERs remaining",  _check_config),
        ("Database — accessible and healthy",    _check_database),
        ("Crunchtime — API reachable",           _check_crunchtime),
        ("SOAP server — running on port 8000",   _check_soap_server),
        ("ngrok — tunnel active",                _check_ngrok),
        ("Last sync — within 25 hours",         _check_last_sync),
        ("Failed syncs — none outstanding",      _check_no_failures),
    ]

    all_pass = True
    for label, fn in checks:
        status, detail = _run_check(fn)
        icon = "✓" if status == 'PASS' else ("⚠" if status == 'WARN' else "✗")
        color_start = '\033[92m' if status == 'PASS' else ('\033[93m' if status == 'WARN' else '\033[91m')
        color_end   = '\033[0m'
        print(f"  {color_start}{icon} {status:4s}{color_end}  {label}")
        if detail:
            print(f"         {detail}")
        if status == 'FAIL':
            all_pass = False

    print()
    if all_pass:
        print("  \033[92mAll checks passed. System is healthy.\033[0m")
    else:
        print("  \033[91mOne or more checks failed. See details above.\033[0m")
    print()
    return all_pass


def _run_check(fn):
    """Run a single check function, catching unexpected exceptions."""
    try:
        return fn()
    except Exception as exc:
        return ('FAIL', f"Unexpected error: {exc}")


# ---------------------------------------------------------------------------
# Individual check functions — each returns (status, detail_string)
# status: 'PASS' | 'WARN' | 'FAIL'
# ---------------------------------------------------------------------------

def _check_config():
    import inspect
    bad = {
        k: v for k, v in vars(config).items()
        if not k.startswith('_') and isinstance(v, str) and 'PLACEHOLDER' in v
    }
    if not bad:
        return ('PASS', None)
    return ('FAIL', f"{len(bad)} PLACEHOLDERs still set: {', '.join(bad.keys())}")


def _check_database():
    db_path = config.SYNC_DB_PATH
    if not os.path.exists(db_path):
        return ('WARN', f"Database file not found at '{db_path}'. It will be created on first sync.")
    try:
        with sqlite3.connect(db_path) as conn:
            conn.execute("SELECT COUNT(*) FROM sync_log")
        return ('PASS', None)
    except sqlite3.OperationalError as exc:
        return ('FAIL', f"Database error: {exc}")


def _check_crunchtime():
    if config.USE_MOCK_DATA:
        mock_path = os.path.join('mock_data', 'mock_crunchtime_response.json')
        if os.path.exists(mock_path):
            return ('PASS', "USE_MOCK_DATA=True — mock file found")
        return ('FAIL', f"USE_MOCK_DATA=True but mock file not found at {mock_path}")

    if 'PLACEHOLDER' in config.CRUNCHTIME_API_BASE_URL:
        return ('FAIL', "CRUNCHTIME_API_BASE_URL is still a PLACEHOLDER")
    try:
        # Just a HEAD request to confirm the host is reachable
        resp = requests.head(config.CRUNCHTIME_API_BASE_URL, timeout=8)
        return ('PASS', f"Host reachable (HTTP {resp.status_code})")
    except requests.exceptions.ConnectionError:
        return ('FAIL', "Cannot reach Crunchtime API host — check network and CRUNCHTIME_API_BASE_URL")
    except requests.exceptions.Timeout:
        return ('FAIL', "Crunchtime API timed out after 8 seconds")


def _check_soap_server():
    try:
        resp = requests.get(f"http://localhost:{config.SOAP_PORT}/?wsdl", timeout=4)
        if resp.status_code == 200 and 'wsdl' in resp.text.lower():
            return ('PASS', f"SOAP server responding on port {config.SOAP_PORT}")
        return ('WARN', f"SOAP server responded but WSDL looks unexpected (HTTP {resp.status_code})")
    except requests.exceptions.ConnectionError:
        return ('FAIL', f"SOAP server not running on port {config.SOAP_PORT}. Start it with: python main.py serve")
    except requests.exceptions.Timeout:
        return ('FAIL', "SOAP server timed out — may be overloaded")


def _check_ngrok():
    if 'PLACEHOLDER' in config.APP_URL:
        return ('WARN', "APP_URL not set — ngrok URL unknown. Set it in config.py after running ngrok.")
    try:
        resp = requests.get(config.APP_URL, timeout=8)
        return ('PASS', f"ngrok tunnel active: {config.APP_URL}")
    except requests.exceptions.ConnectionError:
        return ('FAIL', f"Cannot reach APP_URL ({config.APP_URL}). Is ngrok running?")
    except requests.exceptions.Timeout:
        return ('WARN', "APP_URL timed out — ngrok may be starting up")


def _check_last_sync():
    sync_tracker.initialize_db()
    rows = sync_tracker.get_recent_syncs(limit=1)
    if not rows:
        return ('WARN', "No sync attempts recorded yet")
    last = rows[0]
    if last['status'] != 'success':
        return ('WARN', f"Last sync on {last['business_date']} was '{last['status']}'")
    ts = datetime.fromisoformat(last['sync_timestamp'])
    age = datetime.utcnow() - ts
    if age > timedelta(hours=25):
        hrs = int(age.total_seconds() / 3600)
        return ('FAIL', f"Last successful sync was {hrs} hours ago (over 25 hours)")
    return ('PASS', f"Last successful sync: {last['business_date']} at {last['sync_timestamp'][:16]}")


def _check_no_failures():
    sync_tracker.initialize_db()
    with sync_tracker._get_connection() as conn:
        count = conn.execute(
            """SELECT COUNT(DISTINCT business_date) FROM sync_log
                WHERE status = 'failed' AND location_id = ?
                  AND business_date NOT IN (
                      SELECT business_date FROM sync_log
                       WHERE status = 'success' AND location_id = ?
                  )""",
            (config.CRUNCHTIME_LOCATION_ID, config.CRUNCHTIME_LOCATION_ID)
        ).fetchone()[0]
    if count == 0:
        return ('PASS', None)
    return ('FAIL', f"{count} date(s) have unresolved failures. Run: python main.py retry")
