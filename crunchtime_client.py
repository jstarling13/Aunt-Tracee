# =============================================================================
# crunchtime_client.py — Fetches daily sales data from Crunchtime
# =============================================================================
# Two modes controlled by config.USE_MOCK_DATA:
#   True  → reads mock_data/mock_crunchtime_response.json  (no internet needed)
#   False → calls the real Crunchtime REST API
# ON-SITE: after filling config.py, set USE_MOCK_DATA = False and test.
# =============================================================================

import json
import os
import logging
from datetime import date

import requests

import config

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SalesData — normalized view of a Crunchtime daily sales response
# ---------------------------------------------------------------------------

class SalesData:
    """Wraps the raw Crunchtime API/mock dict with typed attributes."""

    def __init__(self, raw: dict):
        summary = raw.get('sales_summary', {})
        tender  = raw.get('tender_breakdown', {})
        self.location_id     = raw.get('location_id', config.CRUNCHTIME_LOCATION_ID)
        self.business_date   = raw.get('business_date', date.today().isoformat())
        self.gross_sales     = float(summary.get('gross_sales', 0))
        self.discounts       = float(summary.get('discounts', 0))
        self.promos          = float(summary.get('promos', 0))
        self.net_sales       = float(summary.get('net_sales', 0))
        self.sales_tax       = float(summary.get('sales_tax', 0))
        self.total_collected = float(summary.get('total_collected', 0))
        self.cash            = float(tender.get('cash', {}).get('amount', 0))
        self.credit_card     = float(tender.get('credit_card', {}).get('amount', 0))
        self.gift_card       = float(tender.get('gift_card', {}).get('amount', 0))

    def __repr__(self):
        return (
            f"<SalesData date={self.business_date} "
            f"gross=${self.gross_sales:.2f} tax=${self.sales_tax:.2f}>"
        )


def get_sales_data(sales_date: date) -> dict:
    """
    Return Crunchtime sales data for the given date.
    Delegates to mock or live depending on config.USE_MOCK_DATA.
    """
    if config.USE_MOCK_DATA:
        logger.info("USE_MOCK_DATA=True — loading mock sales data")
        return _load_mock_data(sales_date)
    else:
        logger.info("USE_MOCK_DATA=False — calling Crunchtime API")
        return _fetch_live_data(sales_date)


# ---------------------------------------------------------------------------
# MOCK PATH
# ---------------------------------------------------------------------------

def _load_mock_data(sales_date: date) -> dict:
    """Load mock JSON and patch in the requested date so callers get a
    consistent structure regardless of the date they asked for."""
    mock_path = os.path.join(
        os.path.dirname(__file__), 'mock_data', 'mock_crunchtime_response.json'
    )
    with open(mock_path, 'r') as f:
        data = json.load(f)

    # Overwrite the date in the mock so the qbXML TxnDate is always correct
    data['business_date'] = sales_date.isoformat()
    return data


# ---------------------------------------------------------------------------
# LIVE PATH
# ---------------------------------------------------------------------------

def _fetch_live_data(sales_date: date) -> dict:
    """
    Call the real Crunchtime API.

    ON-SITE: Confirm the exact endpoint path with Crunchtime support or docs.
    The URL pattern below is a common convention — adjust if needed.

    Expected endpoint: GET {BASE_URL}/locations/{LOCATION_ID}/sales?date=YYYY-MM-DD
    Authentication:    Bearer token in Authorization header
    """
    _validate_credentials()

    url = (
        f"{config.CRUNCHTIME_API_BASE_URL}"
        f"/locations/{config.CRUNCHTIME_LOCATION_ID}"
        f"/sales"
    )
    headers = {
        'Authorization': f'Bearer {config.CRUNCHTIME_API_KEY}',
        'Accept': 'application/json',
    }
    params = {'date': sales_date.isoformat()}

    logger.debug("GET %s params=%s", url, params)

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
    except requests.exceptions.HTTPError as exc:
        logger.error("Crunchtime API HTTP error: %s — %s", exc, response.text)
        raise
    except requests.exceptions.RequestException as exc:
        logger.error("Crunchtime API connection error: %s", exc)
        raise

    data = response.json()
    logger.info(
        "Crunchtime returned sales data for %s: gross_sales=%s",
        sales_date,
        data.get('gross_sales', 'N/A'),
    )
    return data


def _validate_credentials():
    """Raise early with a clear message if credentials are still placeholders."""
    errors = []
    if config.CRUNCHTIME_API_BASE_URL == 'PLACEHOLDER':
        errors.append('CRUNCHTIME_API_BASE_URL')
    if config.CRUNCHTIME_API_KEY == 'PLACEHOLDER':
        errors.append('CRUNCHTIME_API_KEY')
    if config.CRUNCHTIME_LOCATION_ID == 'PLACEHOLDER':
        errors.append('CRUNCHTIME_LOCATION_ID')
    if errors:
        raise ValueError(
            f"config.py still has PLACEHOLDER values for: {', '.join(errors)}. "
            "Fill these in before setting USE_MOCK_DATA = False."
        )


# ---------------------------------------------------------------------------
# Convenience wrapper — accepts an ISO date string, returns a SalesData object.
# Used by soap_server.py and main.py.
# ---------------------------------------------------------------------------

def get_daily_sales(business_date: str = None) -> SalesData:
    """
    Fetch sales for the given ISO date string (e.g. '2024-01-15').
    Defaults to today if omitted. Returns a typed SalesData object.
    """
    if business_date is None:
        target = date.today()
    else:
        target = date.fromisoformat(business_date)
    raw = get_sales_data(target)
    return SalesData(raw)
