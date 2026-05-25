@echo off
:: =============================================================================
:: start_sync_server.bat — Starts the Crunchtime sync SOAP server
:: SRG Business Services LLC
:: =============================================================================
:: This script is run automatically by Windows Task Scheduler on boot.
:: It activates the Anaconda environment and starts the SOAP server.
::
:: To run manually: double-click this file or run from Command Prompt
:: =============================================================================

title Crunchtime Sync Server

:: Change to the project directory
cd /d "C:\Users\jacob\OneDrive\EMORY\aunt tracee\crunchtime_qbd_sync"

:: Activate Anaconda base environment
call conda activate base

:: Start the SOAP server (keeps running in this window)
echo Starting Crunchtime Sync SOAP server...
python main.py serve

pause
