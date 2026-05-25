# =============================================================================
# crunchtime_client.py — Fetches weekly sales data from Crunchtime
# SRG Business Services LLC — 13-store Dunkin/Baskin setup
# =============================================================================
# Two modes controlled by config.USE_MOCK_DATA:
#   True  → returns realistic mock data (safe for testing, no credentials needed)
#   False → calls the real Crunchtime REST API
#
# ON-SITE: Fill config.py credentials, set USE_MOCK_DATA = False, then run:
#   python main.py test-mock   to verify the full pipeline first
# =============================================================================

import json
import logging
from datetime import date, timedelta

import requests

import config

logger = logging.getLogger(__name__)


def get_weekly_sales(location: dict, week_start: date, week_end: date) -> dict:
    """
    Return one week of sales data for a single store.

    Args:
        location:   dict from config.LOCATIONS (has crunchtime_id, name, has_baskin)
        week_start: first day of the week (Sunday)
        week_end:   last day of the week (Saturday)

    Returns dict with keys:
        week_start      — 'YYYY-MM-DD'
        week_end        — 'YYYY-MM-DD'
        location_id     — Crunchtime location ID
        store_name      — human-readable store name
        dkn_sales       — Dunkin gross sales for the week
        baskin_sales    — Baskin gross sales (0.0 if no Baskin)
        sales_tax       — sales tax collected
        gift_cards      — gift card redemptions
        employee_tips   — tips payable to staff
        cash            — cash tendered
        amex            — American Express tendered
        mc_visa         — Mastercard/Visa tendered (combined)
        discover        — Discover tendered
        grubhub         — Grubhub orders
        uber_eats       — Uber Eats orders
        door_dash       — DoorDash orders
    """
    if config.USE_MOCK_DATA:
        logger.info("USE_MOCK_DATA=True — returning mock weekly sales for %s", location['name'])
        return _mock_weekly_data(location, week_start, week_end)
    else:
        logger.info("Fetching live Crunchtime data for %s week %s-%s",
                    location['name'], week_start, week_end)
        return _fetch_live_weekly(location, week_start, week_end)


# ---------------------------------------------------------------------------
# MOCK DATA — realistic numbers based on Tracee's actual entry (Entry #668)
# Donuts Franklin Square: $35,773 DKN + $2,579 tax + $503 gift cards + $197 tips
# ---------------------------------------------------------------------------

def _mock_weekly_data(location: dict, week_start: date, week_end: date) -> dict:
    """
    Return mock data that mirrors the structure of Tracee's real QB entries.
    Numbers are based on Entry #668 from Donuts Franklin Square.
    """
    has_baskin = location.get('has_baskin', False)

    return {
        'week_start':    week_start.isoformat(),
        'week_end':      week_end.isoformat(),
        'location_id':   location['crunchtime_id'],
        'store_name':    location['name'],

        # Sales by brand (matches QB accounts 4050 / 4051)
        'dkn_sales':     35773.00,
        'baskin_sales':   1250.00 if has_baskin else 0.00,

        # Liabilities / other credits
        'sales_tax':      2579.00,
        'gift_cards':      503.00,
        'employee_tips':   197.19,

        # Payment method breakdown (for deposit entries, maps to 120x accounts)
        'cash':           8200.00,
        'amex':           9100.00,
        'mc_visa':       14500.00,
        'discover':        1200.00,
        'grubhub':         1500.00,
        'uber_eats':       2100.00,
        'door_dash':       1350.00,
    }


# ---------------------------------------------------------------------------
# LIVE PATH — real Crunchtime API calls
# ---------------------------------------------------------------------------

def _fetch_live_weekly(location: dict, week_start: date, week_end: date) -> dict:
    """
    Call Crunchtime API to get weekly sales totals for one location.

    ON-SITE: Confirm the exact endpoint and field names with Crunchtime support.
    The field mapping below (raw_to_normalized) must match the actual API response.
    Ask Crunchtime: "What fields represent DKN net sales, Baskin net sales,
    sales tax collected, gift card redemptions, and employee tips for a date range?"
    """
    _validate_credentials()

    location_id = location['crunchtime_id']
    url = (
        f"{config.CRUNCHTIME_API_BASE_URL}"
        f"/locations/{location_id}/sales"
    )
    headers = {
        'Authorization': f'Bearer {config.CRUNCHTIME_API_KEY}',
        'Accept': 'application/json',
    }
    params = {
        'start_date': week_start.isoformat(),
        'end_date':   week_end.isoformat(),
    }

    logger.debug("GET %s params=%s", url, params)

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        logger.error("Crunchtime API HTTP error for %s: %s", location['name'], exc)
        raise
    except requests.exceptions.RequestException as exc:
        logger.error("Crunchtime API connection error for %s: %s", location['name'], exc)
        raise

    raw = response.json()

    # ---------------------------------------------------------------------------
    # FIELD MAPPING — based on Tracee's Sigma Computing / Dunkin Sales Summary report
    # Report: app.sigmacomputing.com → Dunkin Sales Summary w/ Charged Tips
    #
    # Sales Mix Detail fields:
    #   DD Net Sales              → dkn_sales   (QB 4050)
    #   BR Net Sales              → baskin_sales (QB 4051)
    #   +Sales Tax                → sales_tax    (QB 210) — dollar amount, not rate
    #   GC Total Transactions     → gift_cards   (QB 1204)
    #   Fee Exempt - Charged Tips → employee_tips (QB 25100)
    #
    # Tender Type fields:
    #   Cash Due                  → cash
    #   Credit Card - Amex        → amex
    #   Credit Card - Mastercard  → mc (combined with Visa below)
    #   Credit Card - Visa        → visa (combined with MC above)
    #   Credit Card - Discover    → discover
    #   Grub Hub Tender           → grubhub
    #   Delivery: Uber Eats       → uber_eats
    #   Delivery: Doordash        → door_dash
    # ---------------------------------------------------------------------------
    return {
        'week_start':    week_start.isoformat(),
        'week_end':      week_end.isoformat(),
        'location_id':   location_id,
        'store_name':    location['name'],

        # Sales by brand → QB credit lines
        'dkn_sales':     float(raw.get('DD Net Sales', raw.get('dd_net_sales', 0))),
        'baskin_sales':  float(raw.get('BR Net Sales', raw.get('br_net_sales', 0))),

        # Other QB credit lines
        'sales_tax':     float(raw.get('+Sales Tax', raw.get('sales_tax', 0))),
        'gift_cards':    float(raw.get('GC Total Transactions', raw.get('gift_cards', 0))),
        'employee_tips': float(raw.get('Fee Exempt - Charged Tips', raw.get('employee_tips', 0))),

        # Payment method breakdown → QB Exchange sub-accounts
        'cash':          float(raw.get('Cash Due', raw.get('cash', 0))),
        'amex':          float(raw.get('Credit Card - Amex', raw.get('amex', 0))),
        'mc_visa':       float(raw.get('Credit Card - Mastercard', 0)) +
                         float(raw.get('Credit Card - Visa', 0)),
        'discover':      float(raw.get('Credit Card - Discover', raw.get('discover', 0))),
        'grubhub':       float(raw.get('Grub Hub Tender', raw.get('grubhub', 0))),
        'uber_eats':     float(raw.get('Delivery: Uber Eats', raw.get('uber_eats', 0))),
        'door_dash':     float(raw.get('Delivery: Doordash', raw.get('door_dash', 0))),
    }


def _validate_credentials():
    errors = []
    if config.CRUNCHTIME_API_BASE_URL == 'PLACEHOLDER':
        errors.append('CRUNCHTIME_API_BASE_URL')
    if config.CRUNCHTIME_API_KEY == 'PLACEHOLDER':
        errors.append('CRUNCHTIME_API_KEY')
    if errors:
        raise ValueError(
            f"config.py still has PLACEHOLDER for: {', '.join(errors)}. "
            "Fill these in before setting USE_MOCK_DATA = False."
        )
