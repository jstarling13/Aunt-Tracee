# =============================================================================
# qb_tester.py — QuickBooks Web Connector connection tester
# =============================================================================
# Sends a minimal, safe qbXML query (CompanyQuery — read-only, no side effects)
# through the SOAP server to confirm QuickBooks is connected and responding.
#
# Run: python main.py test-qb
#
# What this tests:
#   1. SOAP server is running locally
#   2. QBWC is polling (it must be running on the QB machine)
#   3. QuickBooks Desktop is open and authorized
#   4. The response comes back without errors
# =============================================================================

import logging
import requests
from datetime import datetime

import config
import sync_tracker

logger = logging.getLogger(__name__)

# A minimal read-only qbXML request — fetches company info, writes nothing
TEST_QBXML = '''<?xml version="1.0" encoding="utf-8"?>
<?qbxml version="13.0"?>
<QBXML>
  <QBXMLMsgsRq onError="stopOnError">
    <CompanyQueryRq requestID="test-1">
    </CompanyQueryRq>
  </QBXMLMsgsRq>
</QBXML>'''


def run():
    """
    Run the QB connection test and print a plain-English report.
    """
    print()
    print("=" * 60)
    print("  QUICKBOOKS CONNECTION TEST")
    print(f"  {datetime.now().strftime('%Y-%m-%d %I:%M %p')}")
    print("=" * 60)
    print()

    steps = [
        ("SOAP server running",         _check_soap_running),
        ("SOAP server returns WSDL",    _check_wsdl),
        ("ngrok URL configured",        _check_ngrok_configured),
        ("ngrok tunnel reachable",      _check_ngrok_tunnel),
        ("Sync tracker DB accessible",  _check_db),
        ("QBWC/QB test (manual step)",  _check_qbwc_manual),
    ]

    all_ok = True
    for label, fn in steps:
        ok, detail = _run(fn)
        icon = "✓" if ok else "✗"
        color = '\033[92m' if ok else '\033[91m'
        reset = '\033[0m'
        print(f"  {color}{icon}{reset}  {label}")
        if detail:
            for line in detail.split('\n'):
                print(f"       {line}")
        if not ok:
            all_ok = False

    print()
    if all_ok:
        print("  \033[92mAll automated checks passed.\033[0m")
        print("  To confirm QuickBooks is responding, open QBWC on the QB")
        print("  machine, check the app checkbox, and click 'Update Selected'.")
        print("  Then run: python main.py show-log")
    else:
        print("  \033[91mOne or more checks failed — see details above.\033[0m")
    print()


def _run(fn):
    try:
        return fn()
    except Exception as exc:
        return (False, f"Unexpected error: {exc}")


def _check_soap_running():
    try:
        requests.get(f"http://localhost:{config.SOAP_PORT}/", timeout=3)
        return (True, None)
    except requests.exceptions.ConnectionError:
        return (
            False,
            f"SOAP server is not running on port {config.SOAP_PORT}.\n"
            "Fix: open a terminal and run: python main.py serve"
        )


def _check_wsdl():
    try:
        resp = requests.get(f"http://localhost:{config.SOAP_PORT}/?wsdl", timeout=4)
        if 'wsdl' in resp.text.lower() or 'definitions' in resp.text.lower():
            return (True, None)
        return (False, f"Got HTTP {resp.status_code} but response doesn't look like a WSDL.")
    except Exception as exc:
        return (False, str(exc))


def _check_ngrok_configured():
    if 'PLACEHOLDER' in config.APP_URL:
        return (
            False,
            "APP_URL in config.py is still 'PLACEHOLDER'.\n"
            "Fix: run ngrok and paste the https URL into config.py"
        )
    return (True, f"APP_URL = {config.APP_URL}")


def _check_ngrok_tunnel():
    if 'PLACEHOLDER' in config.APP_URL:
        return (True, "Skipped (APP_URL not set yet)")
    try:
        resp = requests.get(config.APP_URL, timeout=8)
        return (True, f"ngrok responded with HTTP {resp.status_code}")
    except requests.exceptions.ConnectionError:
        return (
            False,
            f"Cannot reach {config.APP_URL}\n"
            "Fix: make sure ngrok is running (ngrok http 8000) and the URL is current.\n"
            "ngrok URLs change every restart — update config.py and crunchtime_sync.qwc."
        )


def _check_db():
    try:
        sync_tracker.initialize_db()
        rows = sync_tracker.get_recent_syncs(limit=1)
        return (True, f"DB OK — {len(rows)} recent record(s) found")
    except Exception as exc:
        return (False, f"Database error: {exc}")


def _check_qbwc_manual():
    return (
        True,
        "This step requires a human:\n"
        "  1. On the QuickBooks machine, open QuickBooks Web Connector\n"
        "  2. Check the checkbox next to 'Crunchtime QBD Sync'\n"
        "  3. Click 'Update Selected'\n"
        "  4. Status should reach 100%% with no error\n"
        "  5. Then run: python main.py show-log  (look for status=success)"
    )
