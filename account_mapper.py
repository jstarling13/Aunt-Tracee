# =============================================================================
# account_mapper.py — Interactive CLI tool to map QB account names into config.py
# =============================================================================
# Walks the user through entering each QuickBooks account name one at a time
# with a plain-English explanation, then saves directly into config.py.
#
# Run: python main.py setup-accounts
# =============================================================================

import re
import logging

logger = logging.getLogger(__name__)

# Each entry: (config_variable_name, plain_english_prompt, example)
ACCOUNT_PROMPTS = [
    (
        'QB_ACCOUNT_GROSS_SALES',
        "GROSS SALES ACCOUNT\n"
        "This is where your total sales revenue gets recorded — before any discounts.\n"
        "In QuickBooks, go to: Lists → Chart of Accounts\n"
        "Look for an account under 'Income' that tracks your sales.\n"
        "Example names: 'Sales', 'Food Sales', 'Sales Revenue', 'Sales:Food Sales'",
        'Sales Revenue',
    ),
    (
        'QB_ACCOUNT_DISCOUNTS',
        "DISCOUNTS ACCOUNT\n"
        "This is where discounts, coupons, and comps get recorded.\n"
        "Look for an account that reduces your income (sometimes listed under Income as a negative).\n"
        "Example names: 'Discounts Given', 'Sales Discounts', 'Promotions'",
        'Discounts Given',
    ),
    (
        'QB_ACCOUNT_SALES_TAX',
        "SALES TAX PAYABLE ACCOUNT\n"
        "This is a LIABILITY account where the tax you collected is held until you pay the government.\n"
        "Look under 'Other Current Liabilities' or 'Liabilities'.\n"
        "QuickBooks often creates this automatically.\n"
        "Example names: 'Sales Tax Payable', 'State Tax Payable'",
        'Sales Tax Payable',
    ),
    (
        'QB_ACCOUNT_UNDEPOSITED_FUNDS',
        "UNDEPOSITED FUNDS ACCOUNT\n"
        "This is where money is held after a sale but before it is deposited at the bank.\n"
        "QuickBooks creates this account automatically for almost every company file.\n"
        "Example names: 'Undeposited Funds'",
        'Undeposited Funds',
    ),
]


def run():
    """Interactive account mapping session. Saves results to config.py."""
    print()
    print("=" * 65)
    print("  QUICKBOOKS ACCOUNT SETUP")
    print("=" * 65)
    print()
    print("I will ask you for 4 account names from QuickBooks Desktop.")
    print("For each one, open QuickBooks → Lists → Chart of Accounts")
    print("and copy the name EXACTLY as it appears (capitals matter!).")
    print()
    print("Press Enter after typing each account name.")
    print()

    mappings = {}

    for var_name, prompt_text, example in ACCOUNT_PROMPTS:
        print("-" * 65)
        print(prompt_text)
        print(f"\n  (Example: '{example}')")
        print()

        while True:
            value = input(f"  Enter account name: ").strip()
            if not value:
                print("  Please enter a name — this cannot be left blank.")
                continue
            if 'PLACEHOLDER' in value.upper():
                print("  Please enter the real account name, not 'PLACEHOLDER'.")
                continue
            break

        mappings[var_name] = value
        print(f"  ✓ Saved: {var_name} = '{value}'")
        print()

    # Confirm before saving
    print("=" * 65)
    print("  REVIEW YOUR MAPPINGS")
    print("=" * 65)
    for var, val in mappings.items():
        print(f"  {var}")
        print(f"    → '{val}'")
        print()

    confirm = input("Save these to config.py? (yes/no): ").strip().lower()
    if confirm not in ('yes', 'y'):
        print("\nNo changes saved. Run 'python main.py setup-accounts' to try again.")
        return

    _write_to_config(mappings)

    print()
    print("✓ config.py updated successfully!")
    print()
    print("Run 'python main.py validate' to confirm all settings are in place.")
    print()


def _write_to_config(mappings: dict):
    """
    Read config.py, replace the value for each variable, and write it back.
    Uses regex so it works regardless of what the current value is.
    """
    with open('config.py', 'r', encoding='utf-8') as f:
        content = f.read()

    for var_name, new_value in mappings.items():
        # Replace the entire value for this variable (handles any existing string)
        pattern = rf"^({re.escape(var_name)}\s*=\s*)'[^']*'"
        replacement = rf"\1'{new_value}'"
        new_content, count = re.subn(pattern, replacement, content, flags=re.MULTILINE)
        if count == 0:
            logger.warning("Could not find %s in config.py — skipping", var_name)
        else:
            content = new_content
            logger.info("Updated %s in config.py", var_name)

    with open('config.py', 'w', encoding='utf-8') as f:
        f.write(content)
