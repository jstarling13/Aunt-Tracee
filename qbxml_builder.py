# =============================================================================
# qbxml_builder.py — Converts Crunchtime sales data into a qbXML JournalEntry
# =============================================================================
# The output is sent verbatim to QuickBooks Desktop via the Web Connector.
# Conforms to qbXML version 13.0 (compatible with QB Desktop 2013 and later).
#
# Journal entry structure for each sales day:
#   DR  Undeposited Funds       (total cash collected)
#   CR  Gross Sales             (revenue before discounts)
#   DR  Discounts               (contra-revenue)
#   CR  Sales Tax Payable       (tax liability)
# =============================================================================

from decimal import Decimal, ROUND_HALF_UP
import logging

import config

logger = logging.getLogger(__name__)

# All account name config keys — used by the validator below
ACCOUNT_CONFIG_KEYS = [
    'QB_ACCOUNT_GROSS_SALES',
    'QB_ACCOUNT_DISCOUNTS',
    'QB_ACCOUNT_SALES_TAX',
    'QB_ACCOUNT_UNDEPOSITED_FUNDS',
]


def build_journal_entry_xml(sales_data: dict) -> str:
    """
    Transform a Crunchtime sales dict into a complete qbXML request string.

    Args:
        sales_data: dict returned by crunchtime_client.get_sales_data()

    Returns:
        str: valid qbXML ready to send to QuickBooks via QBWC
    """
    _validate_config()

    business_date = sales_data['business_date']          # 'YYYY-MM-DD'
    location_id   = config.CRUNCHTIME_LOCATION_ID
    ref_number    = f"CT-{location_id}-{business_date}"  # e.g. CT-1042-2024-01-15

    gross_sales = _to_decimal(sales_data.get('gross_sales', 0))
    discounts   = _to_decimal(sales_data.get('discounts', 0))
    promos      = _to_decimal(sales_data.get('promos', 0))
    sales_tax   = _to_decimal(sales_data.get('sales_tax', 0))

    # Total discounts/comps reduces net revenue but we post them as separate debit lines
    total_discounts = discounts + promos

    # Undeposited Funds = what actually came in the door
    # net_sales = gross - discounts - tax (tax is collected on top but owed to govt)
    undeposited = gross_sales - total_discounts  # simplified; adjust per client's accounting method

    logger.info(
        "Building qbXML | date=%s ref=%s gross=%.2f disc=%.2f tax=%.2f undep=%.2f",
        business_date, ref_number, gross_sales, total_discounts, sales_tax, undeposited
    )

    xml = f'''<?xml version="1.0" encoding="utf-8"?>
<?qbxml version="13.0"?>
<QBXML>
  <QBXMLMsgsRq onError="stopOnError">
    <JournalEntryAddRq requestID="1">
      <JournalEntryAdd>
        <TxnDate>{business_date}</TxnDate>
        <RefNumber>{ref_number}</RefNumber>
        <Memo>Crunchtime daily sales import — location {location_id}</Memo>

        <!-- DEBIT: Cash and card receipts held until deposited -->
        <JournalDebitLine>
          <AccountRef>
            <FullName>{config.QB_ACCOUNT_UNDEPOSITED_FUNDS}</FullName>
          </AccountRef>
          <Amount>{_fmt(undeposited)}</Amount>
          <Memo>Undeposited funds — {business_date}</Memo>
        </JournalDebitLine>

        <!-- CREDIT: Gross sales before discounts (income) -->
        <JournalCreditLine>
          <AccountRef>
            <FullName>{config.QB_ACCOUNT_GROSS_SALES}</FullName>
          </AccountRef>
          <Amount>{_fmt(gross_sales)}</Amount>
          <Memo>Gross sales — {business_date}</Memo>
        </JournalCreditLine>

        <!-- DEBIT: Discounts and promos reduce net revenue -->
        <JournalDebitLine>
          <AccountRef>
            <FullName>{config.QB_ACCOUNT_DISCOUNTS}</FullName>
          </AccountRef>
          <Amount>{_fmt(total_discounts)}</Amount>
          <Memo>Discounts/promos — {business_date}</Memo>
        </JournalDebitLine>

        <!-- CREDIT: Sales tax collected, owed to tax authority -->
        <JournalCreditLine>
          <AccountRef>
            <FullName>{config.QB_ACCOUNT_SALES_TAX}</FullName>
          </AccountRef>
          <Amount>{_fmt(sales_tax)}</Amount>
          <Memo>Sales tax payable — {business_date}</Memo>
        </JournalCreditLine>

      </JournalEntryAdd>
    </JournalEntryAddRq>
  </QBXMLMsgsRq>
</QBXML>'''

    return xml


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_decimal(value) -> Decimal:
    """Convert any numeric value to a Decimal rounded to 2 places."""
    return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _fmt(value: Decimal) -> str:
    """Format Decimal as a string with exactly 2 decimal places for qbXML."""
    return f"{value:.2f}"


def _validate_config():
    """
    Raise ValueError if any account name still contains 'PLACEHOLDER'.
    This prevents sending malformed XML to QuickBooks Desktop.
    """
    bad = []
    for key in ACCOUNT_CONFIG_KEYS:
        value = getattr(config, key, '')
        if 'PLACEHOLDER' in value:
            bad.append(key)
    if bad:
        raise ValueError(
            f"The following config.py values must be set before building qbXML: "
            f"{', '.join(bad)}. "
            "Open config.py and replace each PLACEHOLDER with the exact account "
            "name from QuickBooks Desktop → Lists → Chart of Accounts."
        )
