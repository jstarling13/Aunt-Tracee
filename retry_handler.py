# =============================================================================
# retry_handler.py — Automatic retry system + nightly job scheduler
# =============================================================================
# Two responsibilities:
#   1. retry_failed_syncs() — scans the DB for failed attempts and retries them
#      with exponential backoff (2s, 4s, 8s between attempts)
#   2. start_scheduler()   — starts APScheduler background jobs:
#        • nightly sync at SYNC_HOUR:SYNC_MINUTE (default 11:00 PM)
#        • retry pass  at RETRY_HOUR:RETRY_MINUTE (default 11:30 PM)
#
# Called automatically when the SOAP server starts, or manually via:
#   python main.py retry
# =============================================================================

import time
import logging
from datetime import date, timedelta

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

import config
import sync_tracker
import crunchtime_client
import qbxml_builder
import validator
import alerts

logger = logging.getLogger(__name__)

# Backoff delays in seconds between retry attempts (attempt 1, 2, 3)
BACKOFF_SECONDS = [2, 4, 8]


def run_sync_for_date(target_date: date) -> bool:
    """
    Full sync pipeline for a single date.
    Returns True on success, False on failure.
    This is the canonical sync function used by QBWC, retry, backfill, and scheduler.
    """
    logger.info("Running sync for %s", target_date)

    # Fetch data
    try:
        sales_data = crunchtime_client.get_sales_data(target_date)
    except Exception as exc:
        msg = f"Crunchtime API error: {exc}"
        logger.error(msg)
        sync_tracker.record_attempt(target_date, 'failed', error_message=msg)
        alerts.alert_sync_failed(target_date, msg)
        return False

    # Validate
    result = validator.validate(sales_data)
    if not result.is_valid:
        msg = "Validation failed:\n" + result.summary()
        logger.error(msg)
        sync_tracker.record_attempt(target_date, 'failed', error_message=msg)
        alerts.alert_bad_data(target_date, result.errors)
        return False

    # Build qbXML
    try:
        xml = qbxml_builder.build_journal_entry_xml(sales_data)
    except Exception as exc:
        msg = f"qbXML build error: {exc}"
        logger.error(msg)
        sync_tracker.record_attempt(target_date, 'failed', error_message=msg)
        alerts.alert_sync_failed(target_date, msg)
        return False

    # Record as pending — QBWC will update to success/failed via receiveResponseXML
    sync_tracker.record_attempt(target_date, 'pending', qbxml_sent=xml)
    logger.info("Sync queued for %s — QBWC will post and confirm", target_date)
    return True


def retry_failed_syncs():
    """
    Find all 'failed' sync records and retry them up to MAX_RETRY_ATTEMPTS times.
    Uses exponential backoff between attempts.
    Sends a recovery email if a previously-failed date now succeeds.
    """
    logger.info("Retry handler: scanning for failed syncs...")

    with sync_tracker._get_connection() as conn:
        rows = conn.execute(
            """
            SELECT DISTINCT business_date FROM sync_log
             WHERE status = 'failed'
               AND location_id = ?
               AND business_date NOT IN (
                   SELECT business_date FROM sync_log
                    WHERE status = 'success' AND location_id = ?
               )
            ORDER BY business_date
            """,
            (config.CRUNCHTIME_LOCATION_ID, config.CRUNCHTIME_LOCATION_ID)
        ).fetchall()

    failed_dates = [date.fromisoformat(r['business_date']) for r in rows]

    if not failed_dates:
        logger.info("Retry handler: no failed syncs to retry.")
        return

    logger.info("Retry handler: found %d date(s) to retry: %s", len(failed_dates), failed_dates)

    for target_date in failed_dates:
        success = False
        for attempt_num in range(1, config.MAX_RETRY_ATTEMPTS + 1):
            logger.info(
                "Retry attempt %d/%d for %s", attempt_num, config.MAX_RETRY_ATTEMPTS, target_date
            )
            try:
                success = run_sync_for_date(target_date)
                if success:
                    logger.info("Retry succeeded for %s on attempt %d", target_date, attempt_num)
                    alerts.alert_sync_recovered(target_date)
                    break
            except Exception as exc:
                logger.error("Retry attempt %d failed: %s", attempt_num, exc)

            if attempt_num < config.MAX_RETRY_ATTEMPTS:
                delay = BACKOFF_SECONDS[min(attempt_num - 1, len(BACKOFF_SECONDS) - 1)]
                logger.info("Waiting %ds before next retry...", delay)
                time.sleep(delay)

        if not success:
            logger.error(
                "All %d retry attempts exhausted for %s", config.MAX_RETRY_ATTEMPTS, target_date
            )
            alerts.alert_sync_failed(
                target_date,
                f"Exhausted all {config.MAX_RETRY_ATTEMPTS} retry attempts. Manual intervention required."
            )


def run_nightly_sync():
    """Scheduled job: sync yesterday's sales data."""
    logger.info("Nightly sync job triggered by scheduler")
    target_date = date.today() - timedelta(days=config.DEFAULT_LOOKBACK_DAYS)

    if sync_tracker.already_synced(target_date):
        logger.info("Nightly sync: %s already synced, skipping", target_date)
        return

    run_sync_for_date(target_date)


def start_scheduler() -> BackgroundScheduler:
    """
    Start APScheduler background jobs.
    Call this from soap_server.py or main.py serve so the scheduler
    runs alongside the SOAP server in the same process.
    Returns the scheduler instance so the caller can shut it down cleanly.
    """
    scheduler = BackgroundScheduler()

    scheduler.add_job(
        run_nightly_sync,
        CronTrigger(hour=config.SYNC_HOUR, minute=config.SYNC_MINUTE),
        id='nightly_sync',
        name='Nightly Crunchtime sync',
        replace_existing=True,
    )
    logger.info(
        "Scheduled nightly sync at %02d:%02d", config.SYNC_HOUR, config.SYNC_MINUTE
    )

    scheduler.add_job(
        retry_failed_syncs,
        CronTrigger(hour=config.RETRY_HOUR, minute=config.RETRY_MINUTE),
        id='retry_pass',
        name='Retry failed syncs',
        replace_existing=True,
    )
    logger.info(
        "Scheduled retry pass at %02d:%02d", config.RETRY_HOUR, config.RETRY_MINUTE
    )

    scheduler.start()
    logger.info("APScheduler started")
    return scheduler
