@echo off
:: ============================================================
:: install.bat — Windows setup script for Crunchtime QBD Sync
:: Run this ONCE on the aunt's computer to set everything up.
:: Double-click this file OR run it from Command Prompt.
:: ============================================================

echo.
echo ============================================================
echo   CRUNCHTIME QBD SYNC — WINDOWS INSTALLER
echo ============================================================
echo.

:: --- Check Python version ---
echo [1/5] Checking Python version...
python --version 2>NUL
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Python is not installed or not on PATH.
    echo Please install Python 3.9+ from https://python.org
    echo Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)
for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo Python %PYVER% found. OK
echo.

:: --- Create virtual environment ---
echo [2/5] Creating virtual environment (venv)...
if exist venv (
    echo Virtual environment already exists - skipping creation.
) else (
    python -m venv venv
    if %ERRORLEVEL% NEQ 0 (
        echo ERROR: Could not create virtual environment.
        pause
        exit /b 1
    )
    echo Virtual environment created.
)
echo.

:: --- Activate and install requirements ---
echo [3/5] Installing Python packages...
call venv\Scripts\activate.bat
pip install --upgrade pip --quiet
pip install -r requirements.txt
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: pip install failed. Check your internet connection.
    pause
    exit /b 1
)
echo Packages installed successfully.
echo.

:: --- Initialize the database ---
echo [4/5] Initializing sync tracker database...
python -c "import sync_tracker; sync_tracker.initialize_db(); print('Database ready.')"
if %ERRORLEVEL% NEQ 0 (
    echo WARNING: Could not initialize database. It will be created on first run.
)
echo.

:: --- Final checklist ---
echo [5/5] Setup complete!
echo.
echo ============================================================
echo   ON-SITE SETUP CHECKLIST — DO THESE NEXT:
echo ============================================================
echo.
echo   1. Open config.py in Notepad and fill in ALL PLACEHOLDER values:
echo        - CRUNCHTIME_API_BASE_URL, CRUNCHTIME_API_KEY, CRUNCHTIME_LOCATION_ID
echo        - QBWC_PASSWORD
echo        - QB_ACCOUNT_* (four QuickBooks account names)
echo        - Email alert settings (optional but recommended)
echo.
echo   2. Run the account setup wizard:
echo        python main.py setup-accounts
echo.
echo   3. Run validation to confirm all settings are filled in:
echo        python main.py validate
echo.
echo   4. Switch to live data in config.py:
echo        USE_MOCK_DATA = False
echo.
echo   5. Install and start ngrok:
echo        ngrok http 8000
echo      Then paste the https URL into config.py (APP_URL) and crunchtime_sync.qwc
echo.
echo   6. Start the sync server in a NEW terminal window:
echo        python main.py serve
echo.
echo   7. Load crunchtime_sync.qwc into QuickBooks Web Connector
echo.
echo   8. Run the dashboard to confirm everything is working:
echo        python main.py dashboard
echo.
echo   See README.md for full instructions.
echo ============================================================
echo.
pause
