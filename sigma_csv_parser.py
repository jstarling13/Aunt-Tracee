# =============================================================================
# sigma_csv_parser.py — Parses Sigma Computing CSV exports from the
#                        "Dunkin Sales Summary w/ Charged Tips" report
# =============================================================================
# HOW TO USE:
#   1. In Sigma: open the Dunkin Sales Summary report
#   2. Set date range to Sunday-Saturday of the week you want
#   3. Export → Download CSV
#   4. Drop the CSV into the sigma_exports/ folder
#   5. This module reads it and returns the same dict format as crunchtime_client.py
#
# The CSV column names come directly from the Sigma report section headers:
#   Sales Mix Detail  → DD Net Sales, BR Net Sales, +Sales Tax, etc.
#   Tender Type       → Credit Card - Amex, Cash Due, etc.
# =============================================================================

import csv
import os
import logging
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

logger = logging.getLogger(__name__)

SIGMA_EXPORT_DIR = 'sigma_exports'


def parse_sigma_csv(filepath: str, location: dict,
                    week_start: date, week_end: date) -> dict:
    """
    Parse a Sigma Computing CSV export and return a weekly sales dict
    that matches the format expected by qbxml_builder.build_weekly_journal_entry_xml().

    Args:
        filepath:   path to the downloaded Sigma CSV file
        location:   dict from config.LOCATIONS for this store
        week_start: first day of the week (Sunday) as date object
        week_end:   last day of the week (Saturday) as date object

    Returns:
        dict with keys: week_start, week_end, location_id, store_name,
        dkn_sales, baskin_sales, sales_tax, gift_cards, employee_tips,
        cash, amex, mc_visa, discover, grubhub, uber_eats, door_dash
    """
    logger.info("Parsing Sigma CSV: %s for %s", filepath, location['name'])

    # Read all rows into a flat key→value dict
    # Sigma CSVs from this report have two columns: metric name and value
    data = {}
    with open(filepath, newline='', encoding='utf-8-sig') as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 2:
                key   = row[0].strip()
                value = row[1].strip()
                if key:
                    data[key] = value

    logger.debug("Sigma CSV fields found: %s", list(data.keys()))

    def _num(key, *fallback_keys):
        """Extract a numeric value from the CSV, trying multiple key names."""
        for k in (key, *fallback_keys):
            val = data.get(k, '').replace('$', '').replace(',', '').strip()
            if val:
                try:
                    return float(val)
                except ValueError:
                    pass
        return 0.0

    # ---------------------------------------------------------------------------
    # Field mapping — Sigma report column name → our normalized field
    # Based on "Dunkin Sales Summary w/ Charged Tips" report structure
    # ---------------------------------------------------------------------------
    dkn_sales     = _num('DD Net Sales', 'Dunkin Net Sales', 'DD+ BR Net Sales')
    baskin_sales  = _num('BR Net Sales', 'Baskin Net Sales')
    sales_tax     = _num('+Sales Tax', 'Sales Tax', 'GI Description')  # dollar amount
    gift_cards    = _num('GC Total Transactions', 'Gift Card Activation and Reloads')
    employee_tips = _num('Fee Exempt - Charged Tips', 'Charged Tips')

    cash          = _num('Cash Due', 'Cash In')
    amex          = _num('Credit Card - Amex', 'Amex')
    mc            = _num('Credit Card - Mastercard', 'Mastercard')
    visa          = _num('Credit Card - Visa', 'Visa')
    discover      = _num('Credit Card - Discover', 'Discover')
    grubhub       = _num('Grub Hub Tender', 'Grubhub')
    uber_eats     = _num('Delivery: Uber Eats', 'Uber Eats')
    door_dash     = _num('Delivery: Doordash', 'DoorDash', 'Doordash')

    result = {
        'week_start':    week_start.isoformat(),
        'week_end':      week_end.isoformat(),
        'location_id':   location['crunchtime_id'],
        'store_name':    location['name'],
        'dkn_sales':     dkn_sales,
        'baskin_sales':  baskin_sales,
        'sales_tax':     sales_tax,
        'gift_cards':    gift_cards,
        'employee_tips': employee_tips,
        'cash':          cash,
        'amex':          amex,
        'mc_visa':       mc + visa,
        'discover':      discover,
        'grubhub':       grubhub,
        'uber_eats':     uber_eats,
        'door_dash':     door_dash,
    }

    logger.info(
        "Parsed: store=%s dkn=%.2f baskin=%.2f tax=%.2f gifts=%.2f tips=%.2f",
        location['name'], dkn_sales, baskin_sales, sales_tax, gift_cards, employee_tips
    )
    return result


def find_latest_export(location_id: str) -> str | None:
    """
    Find the most recently modified CSV in sigma_exports/ for a given location.
    Sigma export filenames typically include the location ID.
    Returns the file path, or None if nothing found.
    """
    if not os.path.isdir(SIGMA_EXPORT_DIR):
        return None

    candidates = []
    for fname in os.listdir(SIGMA_EXPORT_DIR):
        if fname.endswith('.csv') and location_id in fname:
            fpath = os.path.join(SIGMA_EXPORT_DIR, fname)
            candidates.append((os.path.getmtime(fpath), fpath))

    if not candidates:
        # Fall back to most recent CSV regardless of name
        for fname in os.listdir(SIGMA_EXPORT_DIR):
            if fname.endswith('.csv'):
                fpath = os.path.join(SIGMA_EXPORT_DIR, fname)
                candidates.append((os.path.getmtime(fpath), fpath))

    if not candidates:
        return None

    candidates.sort(reverse=True)
    return candidates[0][1]


def list_exports() -> list:
    """Return all CSV files in sigma_exports/ with their modification times."""
    if not os.path.isdir(SIGMA_EXPORT_DIR):
        return []
    files = []
    for fname in sorted(os.listdir(SIGMA_EXPORT_DIR)):
        if fname.endswith('.csv'):
            fpath = os.path.join(SIGMA_EXPORT_DIR, fname)
            mtime = os.path.getmtime(fpath)
            files.append({'name': fname, 'path': fpath, 'mtime': mtime})
    return files
