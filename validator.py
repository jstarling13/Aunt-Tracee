# =============================================================================
# validator.py — Data validation layer for Crunchtime sales records
# =============================================================================
# Every sales record passes through here before being transformed into qbXML.
# Invalid records are logged and skipped — the system never crashes on bad data.
#
# Test from command line: python main.py validate-data
# =============================================================================

import logging
from datetime import date

import config
import sync_tracker

logger = logging.getLogger(__name__)

REQUIRED_FIELDS = ['business_date', 'gross_sales', 'discounts', 'sales_tax']


class ValidationResult:
    """Holds the outcome of validating one sales record."""
    def __init__(self):
        self.errors   = []   # list of error strings
        self.warnings = []   # list of warning strings

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def add_error(self, msg: str):
        self.errors.append(msg)
        logger.warning("VALIDATION ERROR: %s", msg)

    def add_warning(self, msg: str):
        self.warnings.append(msg)
        logger.info("VALIDATION WARNING: %s", msg)

    def summary(self) -> str:
        lines = []
        if self.errors:
            lines.append(f"  ERRORS ({len(self.errors)}):")
            lines.extend(f"    ✗ {e}" for e in self.errors)
        if self.warnings:
            lines.append(f"  WARNINGS ({len(self.warnings)}):")
            lines.extend(f"    ⚠ {w}" for w in self.warnings)
        if self.is_valid and not self.warnings:
            lines.append("  ✓ All checks passed")
        return '\n'.join(lines)


def validate(sales_data: dict, skip_duplicate_check: bool = False) -> ValidationResult:
    """
    Run all validation checks on a Crunchtime sales record.

    Args:
        sales_data: dict from crunchtime_client.get_sales_data()
        skip_duplicate_check: set True during backfill preview to avoid false positives

    Returns:
        ValidationResult — check .is_valid before proceeding
    """
    result = ValidationResult()

    # 1. Required fields present
    for field in REQUIRED_FIELDS:
        if field not in sales_data or sales_data[field] is None:
            result.add_error(f"Missing required field: '{field}'")

    if not result.is_valid:
        # Can't run numeric checks without the basic fields
        return result

    business_date_str = sales_data.get('business_date', '')
    gross_sales       = _to_float(sales_data.get('gross_sales', 0))
    discounts         = _to_float(sales_data.get('discounts', 0))
    promos            = _to_float(sales_data.get('promos', 0))
    sales_tax         = _to_float(sales_data.get('sales_tax', 0))
    tender            = sales_data.get('tender', {})

    # 2. Date format and not in the future
    try:
        record_date = date.fromisoformat(business_date_str)
        if record_date > date.today():
            result.add_error(
                f"Business date {business_date_str} is in the future — cannot sync future dates"
            )
    except ValueError:
        result.add_error(f"Invalid date format: '{business_date_str}' (expected YYYY-MM-DD)")
        return result

    # 3. No negative gross sales
    if gross_sales < 0:
        result.add_error(f"Gross sales is negative: {gross_sales:.2f}")

    # 4. Discounts do not exceed gross sales
    total_discounts = discounts + promos
    if total_discounts > gross_sales and gross_sales > 0:
        result.add_error(
            f"Total discounts ({total_discounts:.2f}) exceed gross sales ({gross_sales:.2f})"
        )

    # 5. Sales tax within configured percentage range
    if gross_sales > 0:
        tax_pct = (sales_tax / gross_sales) * 100
        if tax_pct < config.SALES_TAX_MIN_PCT:
            result.add_error(
                f"Sales tax rate {tax_pct:.2f}% is below minimum "
                f"{config.SALES_TAX_MIN_PCT}% (SALES_TAX_MIN_PCT in config.py)"
            )
        elif tax_pct > config.SALES_TAX_MAX_PCT:
            result.add_error(
                f"Sales tax rate {tax_pct:.2f}% exceeds maximum "
                f"{config.SALES_TAX_MAX_PCT}% (SALES_TAX_MAX_PCT in config.py)"
            )

    # 6. Tender amounts sum to net sales (if tender data is present)
    if tender:
        tender_total = sum(_to_float(v) for v in tender.values())
        net_sales    = gross_sales - total_discounts
        if abs(tender_total - net_sales) > 0.02:   # allow 2-cent rounding tolerance
            result.add_warning(
                f"Tender total ({tender_total:.2f}) does not match net sales ({net_sales:.2f}) "
                f"— difference: {abs(tender_total - net_sales):.2f}"
            )

    # 7. Sanity cap on gross sales
    if gross_sales > config.MAX_GROSS_SALES:
        result.add_warning(
            f"Gross sales {gross_sales:.2f} exceeds MAX_GROSS_SALES "
            f"({config.MAX_GROSS_SALES}) — verify this is correct"
        )

    # 8. Duplicate sync check
    if not skip_duplicate_check and sync_tracker.already_synced(record_date):
        result.add_error(
            f"Date {business_date_str} has already been successfully synced. "
            "Use backfill with --force to override (not recommended)."
        )

    return result


def _to_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
