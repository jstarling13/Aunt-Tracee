# =============================================================================
# config.py — Central configuration for Crunchtime → QuickBooks Desktop sync
# =============================================================================
# HOW TO USE THIS FILE ON-SITE:
#   1. Read every PLACEHOLDER line top to bottom
#   2. Replace each PLACEHOLDER string with the real value
#   3. Do NOT change any other variable names — the rest of the code imports them
#   Run: python main.py validate   to confirm all PLACEHOLDERs are filled in.
# =============================================================================

# -----------------------------------------------------------------------------
# CRUNCHTIME API SETTINGS
# Where to find these: Crunchtime account owner or IT contact provides them.
# Log in to Crunchtime back-office portal → Settings → API/Integrations.
# -----------------------------------------------------------------------------

CRUNCHTIME_API_BASE_URL = 'PLACEHOLDER'   # e.g. 'https://api.crunchtime.com/v2'
CRUNCHTIME_API_KEY      = 'PLACEHOLDER'   # e.g. 'ct_live_abc123xyz...'
CRUNCHTIME_LOCATION_ID  = 'PLACEHOLDER'   # e.g. '1042'  (Locations → your restaurant → Location ID)

# -----------------------------------------------------------------------------
# MOCK DATA TOGGLE
# True  → offline mock data (safe for testing before on-site)
# False → real Crunchtime API calls (fill credentials above first)
# -----------------------------------------------------------------------------
USE_MOCK_DATA = True

# -----------------------------------------------------------------------------
# QUICKBOOKS WEB CONNECTOR (QBWC)
# You choose these credentials — they don't come from QuickBooks.
# Enter the same values when loading crunchtime_sync.qwc into QBWC.
# -----------------------------------------------------------------------------
QBWC_USERNAME = 'integration_user'
QBWC_PASSWORD = 'SRG$ync2024!'            # QBWC password — enter this in QBWC password field

# Public URL of your SOAP server (via ngrok). Run: ngrok http 8000
# Example: 'https://a1b2-12-34-56-78.ngrok-free.app'
APP_URL = 'https://antidote-upswing-reseller.ngrok-free.dev'

# -----------------------------------------------------------------------------
# QUICKBOOKS DESKTOP — CHART OF ACCOUNTS
# Must match EXACTLY what appears in QB Desktop: Lists → Chart of Accounts
# -----------------------------------------------------------------------------
QB_ACCOUNT_GROSS_SALES        = 'Food Sales'
QB_ACCOUNT_DISCOUNTS          = 'Discounts Given'
QB_ACCOUNT_SALES_TAX          = 'Sales Tax Payable'
QB_ACCOUNT_UNDEPOSITED_FUNDS  = 'Undeposited Funds'

# -----------------------------------------------------------------------------
# EMAIL ALERTS
# Used by alerts.py to notify your aunt of sync failures/successes.
# ON-SITE: Use a Gmail account with an App Password (not the regular password).
# To get a Gmail App Password:
#   1. Go to myaccount.google.com → Security → 2-Step Verification (enable it)
#   2. Then go to myaccount.google.com → Security → App Passwords
#   3. Create one named "Crunchtime Sync" — copy the 16-char password
# -----------------------------------------------------------------------------
ALERT_EMAIL_TO       = 'PLACEHOLDER'    # aunt's email address, e.g. 'aunt@gmail.com'
ALERT_EMAIL_FROM     = 'PLACEHOLDER'    # sending Gmail address, e.g. 'myaccount@gmail.com'
SMTP_HOST            = 'smtp.gmail.com'
SMTP_PORT            = 587
SMTP_USERNAME        = 'PLACEHOLDER'    # same as ALERT_EMAIL_FROM
SMTP_PASSWORD        = 'PLACEHOLDER'    # Gmail App Password (16 chars, no spaces)

# Set to True to actually send emails; False to log them without sending (safe for testing)
ALERTS_ENABLED = False  # flip to True after verifying email works with: python main.py test-email

# Contact info shown in GUIDE.md and failure emails
YOUR_CONTACT_NAME  = 'PLACEHOLDER'      # your name
YOUR_CONTACT_PHONE = 'PLACEHOLDER'      # your phone number
YOUR_CONTACT_EMAIL = 'PLACEHOLDER'      # your email address

# -----------------------------------------------------------------------------
# SYNC SCHEDULE (APScheduler — 24-hour time)
# -----------------------------------------------------------------------------
SYNC_HOUR          = 23     # run nightly sync at 11:00 PM
SYNC_MINUTE        = 0
RETRY_HOUR         = 23     # run retry pass at 11:30 PM
RETRY_MINUTE       = 30
MAX_RETRY_ATTEMPTS = 3      # give up after this many consecutive failures per date

# -----------------------------------------------------------------------------
# DATA VALIDATION THRESHOLDS
# Adjust these to match normal sales ranges for this location.
# -----------------------------------------------------------------------------
SALES_TAX_MIN_PCT  = 0.0    # minimum plausible tax rate (0%)
SALES_TAX_MAX_PCT  = 15.0   # maximum plausible tax rate (15%)
MAX_GROSS_SALES    = 50000  # sanity cap — alert if single-day gross exceeds this

# -----------------------------------------------------------------------------
# SOAP SERVER
# -----------------------------------------------------------------------------
SOAP_HOST = '0.0.0.0'
SOAP_PORT = 8000

# Path to the SQLite database
SYNC_DB_PATH = 'sync_tracker.db'

# How many days back to sync by default
DEFAULT_LOOKBACK_DAYS = 1

# Dashboard web server port
DASHBOARD_PORT = 5000
