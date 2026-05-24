# =============================================================================
# alerts.py — Email notification system
# =============================================================================
# Sends your aunt an email when something goes wrong or right.
# Uses Gmail SMTP with an App Password (see config.py for setup instructions).
#
# Test from command line: python main.py test-email
# =============================================================================

import smtplib
import logging
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import config

logger = logging.getLogger(__name__)


def _send(subject: str, body: str):
    """
    Core send function. Respects config.ALERTS_ENABLED.
    If disabled, logs the email instead of sending — safe for dry-run testing.
    """
    if not config.ALERTS_ENABLED:
        logger.info(
            "ALERTS_ENABLED=False — email not sent (would have sent: '%s')", subject
        )
        return

    # Check that SMTP credentials are filled in
    for field in ('ALERT_EMAIL_TO', 'ALERT_EMAIL_FROM', 'SMTP_USERNAME', 'SMTP_PASSWORD'):
        if 'PLACEHOLDER' in str(getattr(config, field, 'PLACEHOLDER')):
            logger.error(
                "Cannot send email — config.%s is still a PLACEHOLDER. "
                "Fill in SMTP settings in config.py.", field
            )
            return

    msg = MIMEMultipart('alternative')
    msg['Subject'] = f"[Crunchtime Sync] {subject}"
    msg['From']    = config.ALERT_EMAIL_FROM
    msg['To']      = config.ALERT_EMAIL_TO

    # Plain-text body
    plain = MIMEText(body, 'plain')
    msg.attach(plain)

    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=15) as server:
            server.ehlo()
            server.starttls()
            server.login(config.SMTP_USERNAME, config.SMTP_PASSWORD)
            server.sendmail(config.ALERT_EMAIL_FROM, config.ALERT_EMAIL_TO, msg.as_string())
        logger.info("Alert email sent to %s: %s", config.ALERT_EMAIL_TO, subject)
    except smtplib.SMTPAuthenticationError:
        logger.error(
            "SMTP authentication failed. Check SMTP_USERNAME and SMTP_PASSWORD in config.py. "
            "Make sure you are using a Gmail App Password, not your regular Gmail password."
        )
    except Exception as exc:
        logger.error("Failed to send alert email: %s", exc, exc_info=True)


# ---------------------------------------------------------------------------
# Public alert functions — call these from other modules
# ---------------------------------------------------------------------------

def alert_sync_failed(business_date, error_message: str):
    subject = f"Sync FAILED for {business_date}"
    body = (
        f"The daily sales sync failed for {business_date}.\n\n"
        f"Error:\n{error_message}\n\n"
        f"The system will automatically retry at {config.RETRY_HOUR}:{config.RETRY_MINUTE:02d} PM.\n\n"
        f"If this keeps happening, contact {config.YOUR_CONTACT_NAME} at "
        f"{config.YOUR_CONTACT_PHONE} or {config.YOUR_CONTACT_EMAIL}.\n\n"
        f"— Crunchtime Sync System"
    )
    _send(subject, body)


def alert_sync_recovered(business_date):
    subject = f"Sync recovered for {business_date}"
    body = (
        f"Good news! The sync for {business_date} succeeded after a previous failure.\n\n"
        f"Everything is working normally now.\n\n"
        f"— Crunchtime Sync System"
    )
    _send(subject, body)


def alert_no_sync_in_25_hours(last_sync_time: datetime):
    subject = "WARNING: No sync in over 25 hours"
    body = (
        f"The last successful sync ran at {last_sync_time.strftime('%Y-%m-%d %I:%M %p')}.\n\n"
        f"That is more than 25 hours ago. Something may be wrong.\n\n"
        f"Steps to check:\n"
        f"  1. Make sure the computer is on and connected to the internet\n"
        f"  2. Open the dashboard (python main.py dashboard) and check the status\n"
        f"  3. If you see errors, contact {config.YOUR_CONTACT_NAME} at {config.YOUR_CONTACT_PHONE}\n\n"
        f"— Crunchtime Sync System"
    )
    _send(subject, body)


def alert_bad_data(business_date, validation_errors: list):
    subject = f"Data warning for {business_date} — sync skipped"
    errors_text = '\n'.join(f"  • {e}" for e in validation_errors)
    body = (
        f"The sales data from Crunchtime for {business_date} had problems and was NOT synced.\n\n"
        f"Issues found:\n{errors_text}\n\n"
        f"This usually means the data in Crunchtime needs to be corrected first.\n\n"
        f"Contact {config.YOUR_CONTACT_NAME} at {config.YOUR_CONTACT_PHONE} for help.\n\n"
        f"— Crunchtime Sync System"
    )
    _send(subject, body)


def alert_test():
    subject = "Test Alert — system is working"
    body = (
        f"This is a test email from the Crunchtime Sync system.\n\n"
        f"If you received this, email alerts are configured correctly!\n\n"
        f"Sent at: {datetime.now().strftime('%Y-%m-%d %I:%M %p')}\n\n"
        f"— Crunchtime Sync System"
    )
    _send(subject, body)
