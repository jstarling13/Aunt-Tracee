@echo off
:: =============================================================================
:: start_ngrok.bat — Starts the ngrok tunnel to expose the SOAP server
:: SRG Business Services LLC
:: =============================================================================
:: Starts ngrok with the reserved domain so the URL never changes.
:: Run AFTER start_sync_server.bat (or they can run simultaneously).
:: =============================================================================

title Crunchtime ngrok Tunnel

echo Starting ngrok tunnel...
ngrok http 127.0.0.1:8000

pause
