# =============================================================================
# config.py — Central configuration for Crunchtime → QuickBooks Desktop sync
# SRG Business Services LLC — 13-store Dunkin/Baskin multi-entity setup
# =============================================================================
# HOW TO USE ON-SITE:
#   1. Fill every PLACEHOLDER from top to bottom
#   2. Run: python main.py validate   to confirm all values are set
#   3. Run: python main.py test-mock  to do a dry run before going live
# =============================================================================

# -----------------------------------------------------------------------------
# CRUNCHTIME API CREDENTIALS
# Get these from whoever manages the Crunchtime account (Uncle Greg / IT contact)
# Log in to Crunchtime back-office portal → Settings → API/Integrations
# -----------------------------------------------------------------------------
CRUNCHTIME_API_BASE_URL = 'PLACEHOLDER'   # e.g. 'https://api.crunchtime.com/v2'
CRUNCHTIME_API_KEY      = 'PLACEHOLDER'   # e.g. 'ct_live_abc123xyz...'

# -----------------------------------------------------------------------------
# MOCK DATA TOGGLE
# True  = use fake data (safe for testing without real credentials)
# False = pull live data from Crunchtime API
# -----------------------------------------------------------------------------
USE_MOCK_DATA = True

# -----------------------------------------------------------------------------
# 13-STORE LOCATION MAP
# Each store needs:
#   crunchtime_id  — the location ID in Crunchtime (get from Crunchtime portal)
#   name           — human-readable store name (for logs and emails)
#   qb_file        — exact path to the QB company file (.qbw) for this store
#   has_baskin     — True if this location also has Baskin-Robbins sales
#
# The account structure is the SAME across all stores (Tracee standardized it).
# Only the QB company file path changes per store.
# -----------------------------------------------------------------------------
LOCATIONS = [
    {
        'crunchtime_id': 'PLACEHOLDER',
        'name':          'Donuts Franklin Square',
        'qb_file':       'PLACEHOLDER',   # e.g. r'C:\QB\FranklinSquare.qbw'
        'has_baskin':    True,
    },
    {
        'crunchtime_id': 'PLACEHOLDER',
        'name':          'Store 2',
        'qb_file':       'PLACEHOLDER',
        'has_baskin':    False,
    },
    {
        'crunchtime_id': 'PLACEHOLDER',
        'name':          'Store 3',
        'qb_file':       'PLACEHOLDER',
        'has_baskin':    False,
    },
    {
        'crunchtime_id': 'PLACEHOLDER',
        'name':          'Store 4',
        'qb_file':       'PLACEHOLDER',
        'has_baskin':    False,
    },
    {
        'crunchtime_id': 'PLACEHOLDER',
        'name':          'Store 5',
        'qb_file':       'PLACEHOLDER',
        'has_baskin':    False,
    },
    {
        'crunchtime_id': 'PLACEHOLDER',
        'name':          'Store 6',
        'qb_file':       'PLACEHOLDER',
        'has_baskin':    False,
    },
    {
        'crunchtime_id': 'PLACEHOLDER',
        'name':          'Store 7',
        'qb_file':       'PLACEHOLDER',
        'has_baskin':    False,
    },
    {
        'crunchtime_id': 'PLACEHOLDER',
        'name':          'Store 8',
        'qb_file':       'PLACEHOLDER',
        'has_baskin':    False,
    },
    {
        'crunchtime_id': 'PLACEHOLDER',
        'name':          'Store 9',
        'qb_file':       'PLACEHOLDER',
        'has_baskin':    False,
    },
    {
        'crunchtime_id': 'PLACEHOLDER',
        'name':          'Store 10',
        'qb_file':       'PLACEHOLDER',
        'has_baskin':    False,
    },
    {
        'crunchtime_id': 'PLACEHOLDER',
        'name':          'Store 11',
        'qb_file':       'PLACEHOLDER',
        'has_baskin':    False,
    },
    {
        'crunchtime_id': 'PLACEHOLDER',
        'name':          'Store 12',
        'qb_file':       'PLACEHOLDER',
        'has_baskin':    False,
    },
    {
        'crunchtime_id': 'PLACEHOLDER',
        'name':          'Store 13',
        'qb_file':       'PLACEHOLDER',
        'has_baskin':    False,
    },
]

# -----------------------------------------------------------------------------
# QUICKBOOKS ACCOUNT NAMES — SAME ACROSS ALL 13 STORES
# Must match EXACTLY what appears in QB Desktop: Lists → Chart of Accounts
# Tracee standardized these account numbers across all company files.
#
# NOTE: QB displays accounts as "NUMBER · Name". In qbXML use the name exactly
# as it appears in QB. Sub-accounts use colon: "Parent Name:Child Name"
# Verify these on-site by opening QB → Lists → Chart of Accounts
# -----------------------------------------------------------------------------

# DEBIT side — the cash clearing/exchange account (acct 120)
QB_ACCOUNT_EXCHANGE         = 'PLACEHOLDER'   # e.g. '120 · Exchange' or just 'Exchange'

# CREDIT side — sales by brand
QB_ACCOUNT_DKN_SALES        = 'PLACEHOLDER'   # e.g. 'Sales:4050 · Sales - Dunkin'
QB_ACCOUNT_BASKIN_SALES     = 'PLACEHOLDER'   # e.g. 'Sales:4051 · Sales - Baskin'

# CREDIT side — other lines
QB_ACCOUNT_SALES_TAX        = 'PLACEHOLDER'   # e.g. '210 · Sales Tax Payable'
QB_ACCOUNT_GIFT_CARDS       = 'PLACEHOLDER'   # e.g. 'Exchange:1204 · Gift Card Exchange'
QB_ACCOUNT_EMPLOYEE_TIPS    = 'PLACEHOLDER'   # e.g. '25100 · Employee Tips Payable'

# Bank account used for deposit entries (acct 100, same in all stores)
QB_ACCOUNT_BANK             = 'PLACEHOLDER'   # e.g. '100 · Checking'

# Payment method sub-accounts under Exchange (acct 120)
QB_ACCOUNT_AMEX             = 'PLACEHOLDER'   # e.g. 'Exchange:1201 · American Express Exchange'
QB_ACCOUNT_MC_VISA          = 'PLACEHOLDER'   # e.g. 'Exchange:1202 · Mastercard/Visa Exchange'
QB_ACCOUNT_DISCOVER         = 'PLACEHOLDER'   # e.g. 'Exchange:1203 · Discover Exchange'
QB_ACCOUNT_GRUBHUB          = 'PLACEHOLDER'   # e.g. 'Exchange:1206 · Grubhub'
QB_ACCOUNT_UBER_EATS        = 'PLACEHOLDER'   # e.g. 'Exchange:1207 · Uber Eats'
QB_ACCOUNT_DOOR_DASH        = 'PLACEHOLDER'   # e.g. 'Exchange:1208 · Door Dash'

# -----------------------------------------------------------------------------
# SYNC SCHEDULE
# Weekly journal entries: Sunday to Saturday week, entry created on Sunday
# The sync fires Sunday night and covers Mon-of-last-week through Sat
# -----------------------------------------------------------------------------
SYNC_DAY_OF_WEEK    = 'sun'    # day to run the weekly sync (APScheduler day name)
SYNC_HOUR           = 23       # 11:00 PM Sunday
SYNC_MINUTE         = 0
RETRY_HOUR          = 23       # 11:30 PM Sunday (retry any failures)
RETRY_MINUTE        = 30
MAX_RETRY_ATTEMPTS  = 3

# Number of days in a sync week (Sun-Sat = 7)
SYNC_WEEK_DAYS      = 7

# -----------------------------------------------------------------------------
# QUICKBOOKS WEB CONNECTOR (QBWC)
# These credentials are shared across all 13 stores — one SOAP server handles all.
# Enter the same password in QBWC when loading each store's .qwc file.
# -----------------------------------------------------------------------------
QBWC_USERNAME = 'integration_user'
QBWC_PASSWORD = 'SRG$ync2024!'

# Public URL of the SOAP server (ngrok tunnel or production server URL)
APP_URL = 'http://localhost:8000'

# -----------------------------------------------------------------------------
# SOAP SERVER
# -----------------------------------------------------------------------------
SOAP_HOST       = '0.0.0.0'
SOAP_PORT       = 8000
SYNC_DB_PATH    = 'sync_tracker.db'
DASHBOARD_PORT  = 5000

# Legacy single-location fallback (used only if LOCATIONS list is not configured)
CRUNCHTIME_LOCATION_ID  = LOCATIONS[0]['crunchtime_id'] if LOCATIONS else 'PLACEHOLDER'
DEFAULT_LOOKBACK_DAYS   = 1

# -----------------------------------------------------------------------------
# EMAIL ALERTS
# Tracee gets notified when a sync fails or recovers.
# Use a Gmail App Password — NOT your regular Gmail password.
# Setup: myaccount.google.com → Security → App Passwords → create "Crunchtime Sync"
# -----------------------------------------------------------------------------
ALERT_EMAIL_TO       = 'PLACEHOLDER'    # Tracee's email
ALERT_EMAIL_FROM     = 'PLACEHOLDER'    # Gmail address sending the alert
SMTP_HOST            = 'smtp.gmail.com'
SMTP_PORT            = 587
SMTP_USERNAME        = 'PLACEHOLDER'    # same as ALERT_EMAIL_FROM
SMTP_PASSWORD        = 'PLACEHOLDER'    # Gmail App Password (16 chars, no spaces)
ALERTS_ENABLED       = False            # flip to True after testing with: python main.py test-email

# Your contact info shown in failure emails
YOUR_CONTACT_NAME    = 'Jacob'
YOUR_CONTACT_PHONE   = 'PLACEHOLDER'
YOUR_CONTACT_EMAIL   = 'PLACEHOLDER'

# -----------------------------------------------------------------------------
# DATA VALIDATION THRESHOLDS
# Adjust per store after first few live syncs
# -----------------------------------------------------------------------------
SALES_TAX_MIN_PCT   = 0.0
SALES_TAX_MAX_PCT   = 15.0
MAX_WEEKLY_SALES    = 500000    # alert if a single week exceeds this across all stores
