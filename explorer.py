# =============================================================================
# explorer.py — CLI data explorer for previewing Crunchtime sales data
# =============================================================================
# Fetches and displays sales data in a formatted table without syncing.
# Safe to run anytime — never writes to the sync tracker or QuickBooks.
#
# Usage:
#   python main.py explore --date 2026-05-22
#   python main.py explore --start 2026-05-01 --end 2026-05-22
# =============================================================================

import time
import logging
from datetime import date, timedelta

import crunchtime_client
import validator

logger = logging.getLogger(__name__)

# Column widths for the display table
COL_WIDTHS = {
    'Date':        12,
    'Gross Sales':  13,
    'Discounts':    12,
    'Promos':       10,
    'Sales Tax':    12,
    'Net Sales':    12,
    'Transactions': 14,
    'Validation':   24,
}


def explore_single(target_date: date):
    """Fetch and display data for a single date."""
    _print_header()
    _print_date_row(target_date)
    _print_footer()


def explore_range(start_date: date, end_date: date):
    """Fetch and display data for a date range."""
    if start_date > end_date:
        print("Error: --start must be before or equal to --end")
        return
    if (end_date - start_date).days > 90:
        print("Warning: exploring more than 90 days may take a while...")

    _print_header()

    current = start_date
    while current <= end_date:
        _print_date_row(current)
        current += timedelta(days=1)
        if current <= end_date:
            time.sleep(0.5)  # be gentle on the API

    _print_footer()


def _print_header():
    print()
    # Build header row
    headers = list(COL_WIDTHS.keys())
    header_line = "  " + "  ".join(h.ljust(COL_WIDTHS[h]) for h in headers)
    separator   = "  " + "  ".join("-" * COL_WIDTHS[h] for h in headers)
    print(header_line)
    print(separator)


def _print_footer():
    print()
    print("  (Preview only — no data was sent to QuickBooks)")
    print()


def _print_date_row(target_date: date):
    """Fetch data for one date and print a single table row."""
    try:
        data = crunchtime_client.get_sales_data(target_date)
    except Exception as exc:
        row = {
            'Date':         target_date.isoformat(),
            'Gross Sales':  f"ERROR",
            'Discounts':    str(exc)[:20],
            'Promos':       '',
            'Sales Tax':    '',
            'Net Sales':    '',
            'Transactions': '',
            'Validation':   '',
        }
        print("  " + "  ".join(str(row.get(h, '')).ljust(COL_WIDTHS[h]) for h in COL_WIDTHS))
        return

    gross   = float(data.get('gross_sales', 0))
    disc    = float(data.get('discounts', 0))
    promos  = float(data.get('promos', 0))
    tax     = float(data.get('sales_tax', 0))
    net     = gross - disc - promos
    txn     = data.get('transaction_count', '—')

    # Run validation silently for the status column
    result = validator.validate(data, skip_duplicate_check=True)
    if result.is_valid and not result.warnings:
        val_str = "OK"
    elif result.is_valid:
        val_str = f"WARN ({len(result.warnings)})"
    else:
        val_str = f"ERR: {result.errors[0][:18]}"

    row = {
        'Date':         target_date.isoformat(),
        'Gross Sales':  f"${gross:,.2f}",
        'Discounts':    f"${disc:,.2f}",
        'Promos':       f"${promos:,.2f}",
        'Sales Tax':    f"${tax:,.2f}",
        'Net Sales':    f"${net:,.2f}",
        'Transactions': str(txn),
        'Validation':   val_str,
    }
    line = "  " + "  ".join(str(row.get(h, '')).ljust(COL_WIDTHS[h]) for h in COL_WIDTHS)
    print(line)
