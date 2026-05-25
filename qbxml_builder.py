# =============================================================================
# qbxml_builder.py — Builds the weekly qbXML journal entry for each store
# =============================================================================
# Matches Tracee's real QuickBooks entry structure:
#
#   DR  120 · Exchange                    (total cash collected for the week)
#   CR  4050 · Sales - Dunkin             (DKN gross sales)
#   CR  4051 · Sales - Baskin             (Baskin sales, if location has it)
#   CR  210  · Sales Tax Payable          (tax collected)
#   CR  1204 · Gift Card Exchange         (gift card redemptions)
#   CR  25100 · Employee Tips Payable     (tips owed to staff)
#
# The entry covers one Sunday-to-Saturday week.
# Entry is created on Sunday night by QBWC calling this server.
# =============================================================================

from decimal import Decimal, ROUND_HALF_UP
from datetime import date, timedelta
import logging

import config

logger = logging.getLogger(__name__)


def get_week_range(sync_date: date = None):
    """
    Returns (week_start, week_end) for the Sunday-Saturday week
    that most recently ended before sync_date.

    If sync_date is Sunday, that Sunday is the last day of the week that ended.
    Week:  Sunday = day 6 in Python's weekday() where Monday = 0
    """
    if sync_date is None:
        sync_date = date.today()

    # Python weekday(): Mon=0, Tue=1, ..., Sun=6
    days_since_sunday = (sync_date.weekday() + 1) % 7
    week_end   = sync_date - timedelta(days=days_since_sunday)      # previous Saturday
    week_start = week_end - timedelta(days=6)                       # the Sunday before that
    return week_start, week_end


def build_weekly_journal_entry_xml(sales_data: dict, location: dict) -> str:
    """
    Build a complete qbXML JournalEntryAdd request for one store's weekly sales.

    Args:
        sales_data: dict returned by crunchtime_client.get_weekly_sales(location, week_start, week_end)
                    Expected keys:
                        week_start      — 'YYYY-MM-DD'
                        week_end        — 'YYYY-MM-DD'
                        dkn_sales       — Dunkin gross sales for the week
                        baskin_sales    — Baskin gross sales (0 if no Baskin)
                        sales_tax       — sales tax collected
                        gift_cards      — gift card redemptions
                        employee_tips   — tips payable to staff
        location:   dict from config.LOCATIONS for this store

    Returns:
        str: qbXML ready to send to QuickBooks via QBWC
    """
    _validate_config()

    week_start  = sales_data['week_start']   # 'YYYY-MM-DD'
    week_end    = sales_data['week_end']     # 'YYYY-MM-DD'
    store_name  = location['name']
    has_baskin  = location.get('has_baskin', False)

    dkn_sales     = _dec(sales_data.get('dkn_sales', 0))
    baskin_sales  = _dec(sales_data.get('baskin_sales', 0)) if has_baskin else _dec(0)
    sales_tax     = _dec(sales_data.get('sales_tax', 0))
    gift_cards    = _dec(sales_data.get('gift_cards', 0))
    employee_tips = _dec(sales_data.get('employee_tips', 0))

    # Total credits must equal the Exchange debit (entry must balance)
    total_credits = dkn_sales + baskin_sales + sales_tax + gift_cards + employee_tips

    # RefNumber: compact week identifier, max 11 chars
    # Format: WYYMMDD (7 chars) — 'W' + year + month + day of week_start
    compact = week_start.replace('-', '')[2:]   # e.g. '260518'
    ref_number = f"W{compact}"                  # e.g. 'W260518' (7 chars)

    logger.info(
        "Building weekly qbXML | store=%s week=%s to %s | "
        "dkn=%.2f baskin=%.2f tax=%.2f gifts=%.2f tips=%.2f total=%.2f",
        store_name, week_start, week_end,
        dkn_sales, baskin_sales, sales_tax, gift_cards, employee_tips, total_credits
    )

    # Build credit lines — one per revenue/liability category
    baskin_line = ''
    if has_baskin and baskin_sales > 0:
        baskin_line = f'''
        <JournalCreditLine>
          <AccountRef><FullName>{config.QB_ACCOUNT_BASKIN_SALES}</FullName></AccountRef>
          <Amount>{_fmt(baskin_sales)}</Amount>
          <Memo>Baskin sales {week_start} to {week_end}</Memo>
        </JournalCreditLine>'''

    xml = f'''<?xml version="1.0" encoding="utf-8"?>
<?qbxml version="13.0"?>
<QBXML>
  <QBXMLMsgsRq onError="stopOnError">
    <JournalEntryAddRq requestID="1">
      <JournalEntryAdd>
        <TxnDate>{week_end}</TxnDate>
        <RefNumber>{ref_number}</RefNumber>
        <Memo>Crunchtime weekly sales {week_start} to {week_end} {store_name}</Memo>
        <JournalDebitLine>
          <AccountRef><FullName>{config.QB_ACCOUNT_EXCHANGE}</FullName></AccountRef>
          <Amount>{_fmt(total_credits)}</Amount>
          <Memo>Weekly cash and card receipts {week_start} to {week_end}</Memo>
        </JournalDebitLine>
        <JournalCreditLine>
          <AccountRef><FullName>{config.QB_ACCOUNT_DKN_SALES}</FullName></AccountRef>
          <Amount>{_fmt(dkn_sales)}</Amount>
          <Memo>Dunkin sales {week_start} to {week_end}</Memo>
        </JournalCreditLine>{baskin_line}
        <JournalCreditLine>
          <AccountRef><FullName>{config.QB_ACCOUNT_SALES_TAX}</FullName></AccountRef>
          <Amount>{_fmt(sales_tax)}</Amount>
          <Memo>Sales tax payable {week_start} to {week_end}</Memo>
        </JournalCreditLine>
        <JournalCreditLine>
          <AccountRef><FullName>{config.QB_ACCOUNT_GIFT_CARDS}</FullName></AccountRef>
          <Amount>{_fmt(gift_cards)}</Amount>
          <Memo>Gift card redemptions {week_start} to {week_end}</Memo>
        </JournalCreditLine>
        <JournalCreditLine>
          <AccountRef><FullName>{config.QB_ACCOUNT_EMPLOYEE_TIPS}</FullName></AccountRef>
          <Amount>{_fmt(employee_tips)}</Amount>
          <Memo>Employee tips payable {week_start} to {week_end}</Memo>
        </JournalCreditLine>
      </JournalEntryAdd>
    </JournalEntryAddRq>
  </QBXMLMsgsRq>
</QBXML>'''

    return xml


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dec(value) -> Decimal:
    return Decimal(str(value)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)


def _fmt(value: Decimal) -> str:
    return f"{value:.2f}"


def _validate_config():
    """Raise if any required QB account name is still PLACEHOLDER."""
    required = {
        'QB_ACCOUNT_EXCHANGE':      config.QB_ACCOUNT_EXCHANGE,
        'QB_ACCOUNT_DKN_SALES':     config.QB_ACCOUNT_DKN_SALES,
        'QB_ACCOUNT_SALES_TAX':     config.QB_ACCOUNT_SALES_TAX,
        'QB_ACCOUNT_GIFT_CARDS':    config.QB_ACCOUNT_GIFT_CARDS,
        'QB_ACCOUNT_EMPLOYEE_TIPS': config.QB_ACCOUNT_EMPLOYEE_TIPS,
    }
    bad = [k for k, v in required.items() if 'PLACEHOLDER' in str(v)]
    if bad:
        raise ValueError(
            f"Fill these config.py values before syncing: {', '.join(bad)}"
        )
