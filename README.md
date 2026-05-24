# Crunchtime → QuickBooks Desktop Sync

Automated daily sync of Crunchtime POS sales data into QuickBooks Desktop journal entries via the QuickBooks Web Connector (QBWC) SOAP protocol.

---

## Pre-Arrival

Everything below is already built and working. The mock data mode lets you verify the full pipeline offline before going on-site.

| Module | File | Purpose |
|---|---|---|
| Configuration | `config.py` | All credentials and settings — fill PLACEHOLDERs on-site |
| SOAP server | `soap_server.py` | Implements all 5 QBWC methods |
| Crunchtime client | `crunchtime_client.py` | Mock + live API modes |
| qbXML builder | `qbxml_builder.py` | Builds JournalEntryAdd for QB |
| Sync tracker | `sync_tracker.py` | SQLite audit log of every sync |
| Data validator | `validator.py` | Checks every record before it hits QB |
| Retry handler | `retry_handler.py` | Auto-retry + APScheduler nightly jobs |
| Email alerts | `alerts.py` | Failure/success/warning notifications |
| Web dashboard | `dashboard.py` | Flask UI for monitoring and manual trigger |
| Account mapper | `account_mapper.py` | Interactive QB account name setup wizard |
| Backfill tool | `backfill.py` | Sync historical date ranges |
| Health checker | `health_check.py` | Full system status report |
| Data explorer | `explorer.py` | Preview Crunchtime data before syncing |
| QB tester | `qb_tester.py` | Verify QBWC connection step by step |
| CLI entry point | `main.py` | All commands in one place |
| QBWC app file | `crunchtime_sync.qwc` | Load into QB Web Connector |
| Mock data | `mock_data/mock_crunchtime_response.json` | Realistic sample sales record |
| Aunt's guide | `GUIDE.md` | Non-technical user guide |
| Windows installer | `install.bat` | One-click environment setup on Windows |
| Mac/Linux installer | `install.sh` | Environment setup on Mac/Linux |

---

## On-Site Setup Checklist

Complete these steps **in order** on your aunt's computer.

### 1. Run the installer

**Windows:** double-click `install.bat`
**Mac/Linux:** `bash install.sh`

This installs all Python packages and initializes the database.

### 2. Set up QuickBooks account names (interactive)

```
python main.py setup-accounts
```

This walks you through each account name with plain-English prompts and saves them directly to `config.py`.

### 3. Fill in remaining config.py values

Open `config.py` and fill in:
- `CRUNCHTIME_API_BASE_URL`, `CRUNCHTIME_API_KEY`, `CRUNCHTIME_LOCATION_ID`
- `QBWC_PASSWORD` (make up a strong password)
- Email alert settings (optional — set `ALERTS_ENABLED = True` after testing)

### 4. Validate config

```
python main.py validate
```

No PLACEHOLDERs should remain.

### 5. Preview data with mock mode

```
python main.py test-mock
python main.py validate-data
```

### 6. Switch to live data

In `config.py`: `USE_MOCK_DATA = False`

### 7. Preview real Crunchtime data

```
python main.py explore --date 2026-05-22
```

### 8. Install and start ngrok

```
ngrok http 8000
```

Copy the https URL. Paste into `config.py` (`APP_URL`) and `crunchtime_sync.qwc`.

### 9. Start the sync server

In a dedicated terminal (leave it running):
```
python main.py serve
```

### 10. Test the connection

```
python main.py health
python main.py test-qb
```

### 11. Load .qwc file into QBWC

1. Open QuickBooks Desktop as Admin
2. Open QuickBooks Web Connector
3. Add Application → select `crunchtime_sync.qwc`
4. Authorize in QuickBooks → enter `QBWC_PASSWORD`
5. Check the app checkbox → Update Selected

### 12. Verify first sync

```
python main.py show-log
python main.py dashboard
```

### 13. Test email alerts

In `config.py`: set `ALERTS_ENABLED = True` and fill in SMTP settings.

```
python main.py test-email
```

### 14. Backfill any historical dates needed

```
python main.py backfill --start 2026-01-01 --end 2026-05-23
```

---

## Commands Reference

| Command | Description |
|---|---|
| `python main.py serve` | Start SOAP server + nightly scheduler (11 PM sync, 11:30 PM retry) |
| `python main.py dashboard` | Open web dashboard at http://localhost:5000 |
| `python main.py health` | Full system health check — pass/fail for every component |
| `python main.py test-mock` | End-to-end mock sync (no QB or Crunchtime needed) |
| `python main.py test-email` | Send a test alert email to verify SMTP settings |
| `python main.py test-qb` | Step-by-step QuickBooks connection tester |
| `python main.py validate` | Check config.py for un-replaced PLACEHOLDERs |
| `python main.py validate-data` | Validate last 30 days of sales data, print full report |
| `python main.py setup-accounts` | Interactive wizard to enter QB account names |
| `python main.py explore --date YYYY-MM-DD` | Preview one day of Crunchtime data |
| `python main.py explore --start DATE --end DATE` | Preview a date range |
| `python main.py backfill --start DATE --end DATE` | Sync historical date range |
| `python main.py backfill ... --force` | Re-sync even already-synced dates |
| `python main.py show-log` | Print 30 most recent sync attempts |
| `python main.py retry` | Manually trigger retry of all failed syncs |

---

## Architecture

```
QBWC (on QB machine)
   │  SOAP/HTTPS
   ▼
ngrok tunnel (public HTTPS → localhost:8000)
   │
   ▼
soap_server.py  (Spyne WSGI — 5 QBWC methods)
   ├─► crunchtime_client.py  →  Crunchtime REST API (or mock JSON)
   ├─► validator.py          →  data integrity checks
   ├─► qbxml_builder.py      →  builds JournalEntryAdd XML
   ├─► sync_tracker.py       →  SQLite audit log
   ├─► retry_handler.py      →  APScheduler (11 PM / 11:30 PM jobs)
   └─► alerts.py             →  email notifications

dashboard.py    (Flask — localhost:5000)
   └─► sync_tracker.py       →  reads history for display
```

---

## Troubleshooting

### 1. QBWC shows "Authentication failed"
`QBWC_USERNAME` and `QBWC_PASSWORD` in `config.py` must match exactly what you entered when loading the `.qwc` file. Re-enter the password in QBWC: right-click the app → Password.

### 2. "Account not found" error in QuickBooks response
The account name in `config.py` does not match QuickBooks Desktop exactly. In QB: Lists → Chart of Accounts. Copy the name character-for-character (case matters). Re-run `python main.py setup-accounts`.

### 3. QBWC can't reach the server
Check three things in order:
1. `python main.py serve` is running in a terminal
2. `ngrok http 8000` is running in another terminal
3. `APP_URL` in `config.py` and `crunchtime_sync.qwc` matches the current ngrok URL (it changes every restart)

### 4. ngrok URL changed after computer restart
Run `ngrok http 8000` again. Copy the new https URL. Update `APP_URL` in `config.py` and both PLACEHOLDER lines in `crunchtime_sync.qwc`. Remove and re-add the app in QBWC (or click the pencil icon if available).

### 5. Still seeing PLACEHOLDER errors
Run `python main.py validate` to see exactly which fields are missing. Then run `python main.py setup-accounts` for the QB account ones.

### 6. Sync shows "pending" forever, never "success"
QBWC hasn't polled yet, or it can't reach the server. Check that QBWC is open, the app is checked, and click "Update Selected" to force a poll. Then check `python main.py show-log`.

### 7. Email alerts not arriving
1. Confirm `ALERTS_ENABLED = True` in `config.py`
2. Confirm you are using a **Gmail App Password** (not your regular password)
3. Check spam/junk folder
4. Run `python main.py test-email` — if it errors, read the error carefully
5. Make sure 2-Step Verification is enabled on the Gmail account

### 8. Crunchtime API returns 401 Unauthorized
`CRUNCHTIME_API_KEY` is wrong or expired. Log into the Crunchtime back-office portal → Settings → API/Integrations and generate a new key.

### 9. Database is corrupted or missing
Run `python main.py health` — it will report the DB status. If corrupted: rename the old `sync_tracker.db` (don't delete — it has history) and re-run `python main.py validate`. A fresh DB will be created on the next sync.

### 10. The computer was restarted and nothing is running
Two programs must always be running:
1. `ngrok http 8000` (in terminal 1)
2. `python main.py serve` (in terminal 2)
Create desktop shortcuts to these commands. After starting both, open the dashboard at http://localhost:5000 and confirm the status shows green.
