#!/usr/bin/env bash
# ============================================================
# install.sh — Mac/Linux setup script for Crunchtime QBD Sync
# Run: bash install.sh
# ============================================================

set -e  # exit immediately on any error

echo ""
echo "============================================================"
echo "  CRUNCHTIME QBD SYNC — MAC/LINUX INSTALLER"
echo "============================================================"
echo ""

# --- Check Python ---
echo "[1/5] Checking Python version..."
if ! command -v python3 &>/dev/null; then
    echo "ERROR: python3 not found."
    echo "On Mac: brew install python3  (or download from python.org)"
    echo "On Linux: sudo apt install python3 python3-pip python3-venv"
    exit 1
fi
PYVER=$(python3 --version)
echo "  $PYVER found. OK"
echo ""

# --- Virtual environment ---
echo "[2/5] Creating virtual environment..."
if [ -d "venv" ]; then
    echo "  Virtual environment already exists — skipping."
else
    python3 -m venv venv
    echo "  Virtual environment created."
fi
echo ""

# --- Install packages ---
echo "[3/5] Installing Python packages..."
source venv/bin/activate
pip install --upgrade pip --quiet
pip install -r requirements.txt
echo "  Packages installed."
echo ""

# --- Initialize database ---
echo "[4/5] Initializing sync tracker database..."
python3 -c "import sync_tracker; sync_tracker.initialize_db(); print('  Database ready.')" || \
    echo "  WARNING: Could not init DB — will be created on first run."
echo ""

# --- Done ---
echo "[5/5] Setup complete!"
echo ""
echo "============================================================"
echo "  ON-SITE SETUP CHECKLIST — DO THESE NEXT:"
echo "============================================================"
echo ""
echo "  1. Edit config.py and fill in ALL PLACEHOLDER values:"
echo "       CRUNCHTIME_API_BASE_URL, CRUNCHTIME_API_KEY, CRUNCHTIME_LOCATION_ID"
echo "       QBWC_PASSWORD"
echo "       QB_ACCOUNT_* (four QuickBooks account names)"
echo ""
echo "  2. Run the account setup wizard:"
echo "       python3 main.py setup-accounts"
echo ""
echo "  3. Validate config is complete:"
echo "       python3 main.py validate"
echo ""
echo "  4. Flip USE_MOCK_DATA = False in config.py"
echo ""
echo "  5. Install and run ngrok:"
echo "       ngrok http 8000"
echo "     Paste the https URL into config.py (APP_URL) and crunchtime_sync.qwc"
echo ""
echo "  6. Start the server:"
echo "       python3 main.py serve"
echo ""
echo "  7. Load crunchtime_sync.qwc into QuickBooks Web Connector"
echo ""
echo "  8. Open the dashboard:"
echo "       python3 main.py dashboard"
echo ""
echo "  See README.md for full step-by-step instructions."
echo "============================================================"
echo ""
