# =============================================================================
# backfill.py — Historical data backfill tool
# =============================================================================
# Syncs Crunchtime sales for any date range into QuickBooks.
# Automatically skips dates already synced (checks sync_tracker DB).
#
# Usage:
#   python main.py backfill --start 2026-01-01 --end 2026-05-31
#   python main.py backfill --start 2026-01-01 --end 2026-05-31 --force
#
# --force skips the duplicate check and re-syncs even already-synced dates.
# =============================================================================

import time
import logging
from datetime import date, timedelta

import config
import sync_tracker
import crunchtime_client
import qbxml_builder
import validator
import alerts

logger = logging.getLogger(__name__)

DELAY_BETWEEN_REQUESTS = 2  # seconds — be polite to the Crunchtime API


def run(start_date: date, end_date: date, force: bool = False):
    """
    Backfill sales data for every day in [start_date, end_date] inclusive.
    Prints a live progress line for each date and a summary report at the end.
    """
    sync_tracker.initialize_db()

    if start_date > end_date:
        print("Error: --start date must be before or equal to --end date.")
        return

    if end_date > date.today():
        print("Error: cannot backfill future dates.")
        return

    total_days = (end_date - start_date).days + 1
    print()
    print("=" * 60)
    print(f"  BACKFILL: {start_date} → {end_date}  ({total_days} days)")
    print(f"  Force re-sync: {'YES' if force else 'NO'}")
    print("=" * 60)
    print()

    succeeded = 0
    failed    = 0
    skipped   = 0
    errors    = []

    current = start_date
    day_num = 0

    while current <= end_date:
        day_num += 1
        pct = int((day_num / total_days) * 100)
        print(f"  [{pct:3d}%] {current}", end="  ", flush=True)

        # Duplicate check (unless --force)
        if not force and sync_tracker.already_synced(current):
            print("SKIPPED (already synced)")
            skipped += 1
            current += timedelta(days=1)
            continue

        # Fetch
        try:
            sales_data = crunchtime_client.get_sales_data(current)
        except Exception as exc:
            msg = f"API error: {exc}"
            print(f"FAILED — {msg}")
            sync_tracker.record_attempt(current, 'failed', error_message=msg)
            errors.append((current, msg))
            failed += 1
            current += timedelta(days=1)
            time.sleep(DELAY_BETWEEN_REQUESTS)
            continue

        # Validate
        result = validator.validate(sales_data, skip_duplicate_check=True)
        if not result.is_valid:
            msg = "Validation: " + "; ".join(result.errors)
            print(f"FAILED — {msg}")
            sync_tracker.record_attempt(current, 'failed', error_message=msg)
            errors.append((current, msg))
            failed += 1
            current += timedelta(days=1)
            time.sleep(DELAY_BETWEEN_REQUESTS)
            continue

        if result.warnings:
            print(f"WARNINGS: {'; '.join(result.warnings)}", end="  ", flush=True)

        # Build XML
        try:
            xml = qbxml_builder.build_journal_entry_xml(sales_data)
        except Exception as exc:
            msg = f"XML build error: {exc}"
            print(f"FAILED — {msg}")
            sync_tracker.record_attempt(current, 'failed', error_message=msg)
            errors.append((current, msg))
            failed += 1
            current += timedelta(days=1)
            time.sleep(DELAY_BETWEEN_REQUESTS)
            continue

        # Record as pending (QBWC will confirm)
        sync_tracker.record_attempt(current, 'pending', qbxml_sent=xml)
        print("QUEUED ✓")
        succeeded += 1

        current += timedelta(days=1)
        if current <= end_date:
            time.sleep(DELAY_BETWEEN_REQUESTS)

    # Summary report
    print()
    print("=" * 60)
    print("  BACKFILL COMPLETE")
    print("=" * 60)
    print(f"  Total dates:  {total_days}")
    print(f"  Queued:       {succeeded}  (pending QBWC pickup)")
    print(f"  Skipped:      {skipped}   (already synced)")
    print(f"  Failed:       {failed}")
    print()

    if errors:
        print("  FAILURES:")
        for d, msg in errors:
            print(f"    {d}: {msg}")
        print()
        print("  Run 'python main.py retry' to attempt failed dates again.")
    else:
        print("  No errors! Run 'python main.py show-log' to review.")
    print()
