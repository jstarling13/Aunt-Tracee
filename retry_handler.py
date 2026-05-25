# =============================================================================
# retry_handler.py — Weekly job scheduler + automatic retry system
# SRG Business Services LLC — 13-store Canyon Donuts
# =============================================================================
# Responsibilities:
#   1. run_weekly_sync()   — fires every Sunday night, syncs all 13 stores
#   2. retry_failed_syncs() — fires 30 min later, retries any that failed
#   3. start_scheduler()   — wires both jobs into APScheduler
#
# The weekly sync just pre-validates and queues data. The actual QB posting
# happens when QBWC polls the SOAP server and calls sendRequestXML.
# =============================================================================

import time
import logging
from datetime import date

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

import config
import sync_tracker
import crunchtime_client
import qbxml_builder
import alerts

logger = logging.getLogger(__name__)

BACKOFF_SECONDS = [2, 4, 8]


def run_weekly_sync():
    """
    Sunday night scheduler job — pre-fetches and validates sales data
    for all 13 stores for the week that just ended (Sun-Sat).
    QBWC picks up the data on its next poll and posts to QuickBooks.
    """
    week_start, week_end = qbxml_builder.get_week_range()
    logger.info("Weekly sync triggered: week %s to %s, %d stores",
                week_start, week_end, len(config.LOCATIONS))

    for location in config.LOCATIONS:
        loc_id = location['crunchtime_id']
        name   = location['name']

        if sync_tracker.already_synced(loc_id, week_start):
            logger.info("Weekly sync: %s week %s already done — skipping", name, week_start)
            continue

        try:
            sales_data = crunchtime_client.get_weekly_sales(location, week_start, week_end)
            xml        = qbxml_builder.build_weekly_journal_entry_xml(sales_data, location)

            sync_tracker.record_attempt(
                location_id   = loc_id,
                store_name    = name,
                week_start    = week_start,
                week_end      = week_end,
                status        = 'pending',
                qbxml_sent    = xml,
            )
            logger.info("Weekly sync: queued %s week %s for QBWC", name, week_start)

        except Exception as exc:
            msg = f"Error fetching/building for {name}: {exc}"
            logger.error(msg, exc_info=True)
            sync_tracker.record_attempt(
                location_id   = loc_id,
                store_name    = name,
                week_start    = week_start,
                week_end      = week_end,
                status        = 'failed',
                error_message = msg,
            )
            alerts.alert_sync_failed(week_start, msg)


def retry_failed_syncs():
    """
    Retry all failed sync attempts that haven't hit the retry limit.
    Fires 30 minutes after the main weekly sync.
    """
    logger.info("Retry handler: scanning for failed syncs...")
    failed = sync_tracker.get_failed_syncs()

    if not failed:
        logger.info("Retry handler: nothing to retry.")
        return

    logger.info("Retry handler: found %d failed attempt(s)", len(failed))

    for row in failed:
        loc_id     = row['location_id']
        store_name = row['store_name']
        week_start = date.fromisoformat(row['week_start'])
        week_end   = date.fromisoformat(row['week_end'])
        location   = _find_location(loc_id)

        if not location:
            logger.error("Cannot retry %s — location not found in config", store_name)
            continue

        # Already succeeded in a later attempt
        if sync_tracker.already_synced(loc_id, week_start):
            logger.info("Retry: %s week %s now shows success — skipping", store_name, week_start)
            continue

        sync_tracker.increment_retry(row['id'])

        for attempt in range(1, config.MAX_RETRY_ATTEMPTS + 1):
            logger.info("Retry %d/%d for %s week %s",
                        attempt, config.MAX_RETRY_ATTEMPTS, store_name, week_start)
            try:
                sales_data = crunchtime_client.get_weekly_sales(location, week_start, week_end)
                xml        = qbxml_builder.build_weekly_journal_entry_xml(sales_data, location)

                sync_tracker.record_attempt(
                    location_id   = loc_id,
                    store_name    = store_name,
                    week_start    = week_start,
                    week_end      = week_end,
                    status        = 'pending',
                    qbxml_sent    = xml,
                )
                logger.info("Retry queued for QBWC: %s week %s", store_name, week_start)
                break

            except Exception as exc:
                logger.error("Retry attempt %d failed for %s: %s", attempt, store_name, exc)
                delay = BACKOFF_SECONDS[min(attempt - 1, len(BACKOFF_SECONDS) - 1)]
                if attempt < config.MAX_RETRY_ATTEMPTS:
                    time.sleep(delay)
                else:
                    alerts.alert_sync_failed(
                        week_start,
                        f"{store_name}: exhausted all {config.MAX_RETRY_ATTEMPTS} retries. "
                        "Manual intervention required."
                    )


def start_scheduler() -> BackgroundScheduler:
    """
    Start APScheduler with two weekly Sunday night jobs.
    Returns the scheduler so the caller can shut it down cleanly.
    """
    scheduler = BackgroundScheduler()

    # Main sync: Sunday at SYNC_HOUR:SYNC_MINUTE (default 11:00 PM)
    scheduler.add_job(
        run_weekly_sync,
        CronTrigger(
            day_of_week = config.SYNC_DAY_OF_WEEK,
            hour        = config.SYNC_HOUR,
            minute      = config.SYNC_MINUTE,
        ),
        id='weekly_sync',
        name='Weekly Crunchtime sync — all 13 stores',
        replace_existing=True,
    )
    logger.info("Scheduled weekly sync: %s at %02d:%02d",
                config.SYNC_DAY_OF_WEEK.upper(), config.SYNC_HOUR, config.SYNC_MINUTE)

    # Retry pass: 30 minutes later
    scheduler.add_job(
        retry_failed_syncs,
        CronTrigger(
            day_of_week = config.SYNC_DAY_OF_WEEK,
            hour        = config.RETRY_HOUR,
            minute      = config.RETRY_MINUTE,
        ),
        id='retry_pass',
        name='Retry failed syncs',
        replace_existing=True,
    )
    logger.info("Scheduled retry pass: %s at %02d:%02d",
                config.SYNC_DAY_OF_WEEK.upper(), config.RETRY_HOUR, config.RETRY_MINUTE)

    scheduler.start()
    logger.info("APScheduler started")
    return scheduler


def _find_location(location_id: str) -> dict | None:
    for loc in config.LOCATIONS:
        if loc['crunchtime_id'] == location_id:
            return loc
    return None
