# =============================================================================
# main.py — Command-line entry point for the Crunchtime QBD Sync system
# =============================================================================
# Usage: python main.py <command> [options]
#
# Commands:
#   serve           Start the SOAP server (+ nightly scheduler)
#   dashboard       Open the web dashboard in your browser
#   health          Run full system health check
#   test-mock       Run a complete end-to-end mock sync (no QB needed)
#   test-email      Send a test alert email (verify SMTP settings)
#   test-qb         Test QuickBooks Web Connector connection
#   validate        Check config.py for un-replaced PLACEHOLDERs
#   validate-data   Validate last 30 days of sales data and print a report
#   setup-accounts  Interactive wizard to map QuickBooks account names
#   explore         Preview Crunchtime sales data in a formatted table
#   backfill        Sync historical data for a date range
#   show-log        Print recent sync history from the database
#   retry           Manually trigger the retry handler
# =============================================================================

import sys
import logging
import argparse
from datetime import date, timedelta
from pprint import pprint

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('logs/main.log'),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

import config
import sync_tracker


# ---------------------------------------------------------------------------
# Command implementations
# ---------------------------------------------------------------------------

def cmd_serve(args):
    """Start the SOAP server with the nightly scheduler attached."""
    import soap_server
    import retry_handler

    sync_tracker.initialize_db()

    # Start background scheduler (nightly sync + retry)
    scheduler = retry_handler.start_scheduler()

    app = soap_server.create_app()
    from wsgiref.simple_server import make_server
    logger.info("SOAP server on %s:%s  |  WSDL: http://localhost:%s/?wsdl",
                config.SOAP_HOST, config.SOAP_PORT, config.SOAP_PORT)
    logger.info("Nightly sync scheduled at %02d:%02d", config.SYNC_HOUR, config.SYNC_MINUTE)
    server = make_server(config.SOAP_HOST, config.SOAP_PORT, app)
    try:
        server.serve_forever()
    finally:
        scheduler.shutdown()


def cmd_dashboard(args):
    """Launch the Flask dashboard and open a browser tab."""
    import dashboard
    sync_tracker.initialize_db()
    dashboard.run_dashboard()


def cmd_health(args):
    """Run the full system health check."""
    import health_check
    health_check.run()


def cmd_test_mock(args):
    """Run a full mock sync without QBWC — verifies the full pipeline."""
    import crunchtime_client
    import qbxml_builder
    import validator

    sync_tracker.initialize_db()
    target_date = date.today() - timedelta(days=config.DEFAULT_LOOKBACK_DAYS)

    print(f"\n{'='*60}\n  TEST MOCK SYNC for date: {target_date}\n{'='*60}\n")

    print("[1] Fetching sales data (USE_MOCK_DATA=%s)..." % config.USE_MOCK_DATA)
    sales_data = crunchtime_client.get_sales_data(target_date)
    pprint(sales_data)

    print("\n[2] Validating data...")
    result = validator.validate(sales_data, skip_duplicate_check=True)
    print(result.summary())
    if not result.is_valid:
        print("\nValidation failed — fix errors above before going live.")
        sys.exit(1)

    print("\n[3] Building qbXML...")
    try:
        xml = qbxml_builder.build_journal_entry_xml(sales_data)
        print(xml)
    except ValueError as exc:
        print(f"\nCONFIG ERROR: {exc}")
        print("Fill in QB_ACCOUNT_* values in config.py (or run: python main.py setup-accounts)")
        sys.exit(1)

    print("\n[4] Recording sync attempt...")
    row_id = sync_tracker.record_attempt(target_date, 'pending', qbxml_sent=xml)
    mock_resp = '<QBXML><QBXMLMsgsRs><JournalEntryAddRs statusCode="0" statusSeverity="Info" statusMessage="Status OK"/></QBXMLMsgsRs></QBXML>'
    sync_tracker.update_attempt(row_id=row_id, status='success', qb_response=mock_resp)
    print(f"  Row ID: {row_id}  →  status: success")

    print(f"\n{'='*60}\n  Mock sync complete. Run 'python main.py show-log' to verify.\n{'='*60}\n")


def cmd_test_email(args):
    """Send a test alert email to verify SMTP settings."""
    import alerts
    print("\nSending test email to %s..." % config.ALERT_EMAIL_TO)
    if not config.ALERTS_ENABLED:
        print("NOTE: ALERTS_ENABLED=False in config.py")
        print("The email was NOT sent — set ALERTS_ENABLED=True and fill in SMTP settings first.")
        print("Simulated email content would be a test alert.")
        return
    alerts.alert_test()
    print("Done. Check your inbox at %s." % config.ALERT_EMAIL_TO)


def cmd_test_qb(args):
    """Run the QuickBooks connection tester."""
    import qb_tester
    qb_tester.run()


def cmd_validate(args):
    """Check config.py for remaining PLACEHOLDER values."""
    bad = {
        k: v for k, v in vars(config).items()
        if not k.startswith('_') and isinstance(v, str) and 'PLACEHOLDER' in v
    }
    if bad:
        print(f"\nThe following config.py values still need to be filled in ({len(bad)} total):\n")
        for k, v in bad.items():
            print(f"  {k}")
        print("\nOpen config.py and replace each PLACEHOLDER with the real value.")
        print("Run: python main.py setup-accounts  to set QB account names interactively.\n")
    else:
        print("\nAll config.py values look filled in (no PLACEHOLDER strings found).\n")
        print("Next step: python main.py health\n")


def cmd_validate_data(args):
    """Validate the last 30 days of sales data and print a full report."""
    import crunchtime_client
    import validator

    print(f"\n{'='*60}\n  DATA VALIDATION REPORT — LAST 30 DAYS\n{'='*60}\n")

    today = date.today()
    total = passed = failed = warned = 0

    for i in range(29, -1, -1):
        d = today - timedelta(days=i)
        total += 1
        try:
            data = crunchtime_client.get_sales_data(d)
            result = validator.validate(data, skip_duplicate_check=True)
        except Exception as exc:
            print(f"  {d}  ERROR — {exc}")
            failed += 1
            continue

        if result.is_valid and not result.warnings:
            print(f"  {d}  OK")
            passed += 1
        elif result.is_valid:
            print(f"  {d}  WARNINGS ({len(result.warnings)}):")
            for w in result.warnings:
                print(f"           ⚠ {w}")
            warned += 1
            passed += 1
        else:
            print(f"  {d}  FAILED ({len(result.errors)} error(s)):")
            for e in result.errors:
                print(f"           ✗ {e}")
            failed += 1

    print(f"\n{'='*60}")
    print(f"  Total: {total}  |  Passed: {passed}  |  Warnings: {warned}  |  Failed: {failed}")
    print(f"{'='*60}\n")


def cmd_setup_accounts(args):
    """Interactive wizard to map QuickBooks account names into config.py."""
    import account_mapper
    account_mapper.run()


def cmd_explore(args):
    """Preview Crunchtime sales data in a formatted table."""
    import explorer
    if args.date:
        try:
            d = date.fromisoformat(args.date)
        except ValueError:
            print("Error: --date must be in YYYY-MM-DD format")
            sys.exit(1)
        explorer.explore_single(d)
    elif args.start and args.end:
        try:
            start = date.fromisoformat(args.start)
            end   = date.fromisoformat(args.end)
        except ValueError:
            print("Error: --start and --end must be in YYYY-MM-DD format")
            sys.exit(1)
        explorer.explore_range(start, end)
    else:
        # Default: last 7 days
        explorer.explore_range(date.today() - timedelta(days=6), date.today())


def cmd_backfill(args):
    """Sync historical sales data for a date range."""
    import backfill as backfill_mod
    try:
        start = date.fromisoformat(args.start)
        end   = date.fromisoformat(args.end)
    except (ValueError, AttributeError):
        print("Usage: python main.py backfill --start YYYY-MM-DD --end YYYY-MM-DD")
        sys.exit(1)
    force = getattr(args, 'force', False)
    sync_tracker.initialize_db()
    backfill_mod.run(start, end, force=force)


def cmd_show_log(args):
    """Print the 30 most recent sync attempts."""
    sync_tracker.initialize_db()
    rows = sync_tracker.get_recent_syncs(limit=30)
    if not rows:
        print("\nNo sync attempts recorded yet.\n")
        return
    print(f"\n{'='*80}")
    print(f"  RECENT SYNC ATTEMPTS (most recent first)")
    print(f"{'='*80}")
    print(f"  {'ID':<5} {'Date':<14} {'Status':<10} {'Timestamp':<20} Error")
    print(f"  {'-'*5} {'-'*14} {'-'*10} {'-'*20} {'-'*20}")
    for r in rows:
        err = (r['error_message'] or '')[:40]
        print(
            f"  {r['id']:<5} {r['business_date']:<14} {r['status']:<10} "
            f"{r['sync_timestamp'][:19]:<20} {err}"
        )
    print()


def cmd_retry(args):
    """Manually trigger the retry handler for all failed syncs."""
    import retry_handler
    sync_tracker.initialize_db()
    print("\nScanning for failed syncs to retry...\n")
    retry_handler.retry_failed_syncs()
    print("\nRetry pass complete. Run 'python main.py show-log' to see results.\n")


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='python main.py',
        description='Crunchtime → QuickBooks Desktop Sync'
    )
    sub = parser.add_subparsers(dest='command', metavar='<command>')

    sub.add_parser('serve',         help='Start SOAP server + nightly scheduler')
    sub.add_parser('dashboard',     help='Open web dashboard in browser')
    sub.add_parser('health',        help='Run full system health check')
    sub.add_parser('test-mock',     help='Run end-to-end mock sync (no QB needed)')
    sub.add_parser('test-email',    help='Send a test alert email')
    sub.add_parser('test-qb',       help='Test QuickBooks Web Connector connection')
    sub.add_parser('validate',      help='Check config.py for PLACEHOLDERs')
    sub.add_parser('validate-data', help='Validate last 30 days of sales data')
    sub.add_parser('setup-accounts',help='Interactive QB account name mapper')
    sub.add_parser('show-log',      help='Print recent sync history')
    sub.add_parser('retry',         help='Manually retry all failed syncs')

    # explore
    p_explore = sub.add_parser('explore', help='Preview sales data in terminal table')
    p_explore.add_argument('--date',  help='Single date: YYYY-MM-DD')
    p_explore.add_argument('--start', help='Range start: YYYY-MM-DD')
    p_explore.add_argument('--end',   help='Range end: YYYY-MM-DD')

    # backfill
    p_backfill = sub.add_parser('backfill', help='Sync historical data for a date range')
    p_backfill.add_argument('--start', required=True, help='Start date: YYYY-MM-DD')
    p_backfill.add_argument('--end',   required=True, help='End date: YYYY-MM-DD')
    p_backfill.add_argument('--force', action='store_true',
                            help='Re-sync even already-synced dates')

    return parser


COMMAND_MAP = {
    'serve':          cmd_serve,
    'dashboard':      cmd_dashboard,
    'health':         cmd_health,
    'test-mock':      cmd_test_mock,
    'test-email':     cmd_test_email,
    'test-qb':        cmd_test_qb,
    'validate':       cmd_validate,
    'validate-data':  cmd_validate_data,
    'setup-accounts': cmd_setup_accounts,
    'explore':        cmd_explore,
    'backfill':       cmd_backfill,
    'show-log':       cmd_show_log,
    'retry':          cmd_retry,
}


if __name__ == '__main__':
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        print()
        print("Available commands:")
        for cmd, fn in COMMAND_MAP.items():
            print(f"  {cmd:<18} {fn.__doc__}")
        print()
        sys.exit(0)

    if args.command not in COMMAND_MAP:
        print(f"Unknown command: {args.command}")
        parser.print_help()
        sys.exit(1)

    COMMAND_MAP[args.command](args)
