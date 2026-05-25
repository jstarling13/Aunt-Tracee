# =============================================================================
# soap_server.py — SOAP server implementing the QuickBooks Web Connector protocol
# =============================================================================
# QuickBooks Web Connector (QBWC) connects to this server and calls six methods
# in sequence each sync cycle. Spyne maps Python functions to SOAP operations.
#
# QBWC call order each sync cycle:
#   1. serverVersion      — version handshake
#   2. clientVersion      — version handshake
#   3. authenticate       — credential check, returns session ticket
#   4. sendRequestXML     — we return qbXML; QB processes it
#   5. receiveResponseXML — QB returns its response; we log it
#   6. closeConnection    — cycle complete
#
# Run:  python soap_server.py
# Port: config.SOAP_PORT (default 8000)
# =============================================================================

import logging
import os
import uuid
import xml.etree.ElementTree as ET
from datetime import date, timedelta

from spyne import Application, rpc, ServiceBase, Unicode, Integer, Iterable
from spyne.protocol.soap import Soap11
from spyne.server.wsgi import WsgiApplication
from wsgiref.simple_server import make_server

import config
import crunchtime_client
import qbxml_builder
import sync_tracker

os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('logs/soap_server.log'),
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger(__name__)

# Module-level state for the current sync cycle.
# QBWC calls methods sequentially in one session, so this is safe.
_state = {
    'row_id':      None,
    'target_date': None,
}

QBWC_NS = 'http://developer.intuit.com/'


class QBWebConnectorService(ServiceBase):
    """
    Implements the six QBWC SOAP methods.
    @rpc type list must match parameter count exactly (excluding ctx).
    """

    # ------------------------------------------------------------------
    # serverVersion(ticket) → str
    # ------------------------------------------------------------------
    @rpc(Unicode, _returns=Unicode)
    def serverVersion(ctx, ticket):
        logger.info("QBWC: serverVersion")
        return '1.0.0'

    # ------------------------------------------------------------------
    # clientVersion(strVersion) → str
    # Return '' = ok, 'W:msg' = warning, 'E:msg' = reject
    # ------------------------------------------------------------------
    @rpc(Unicode, _returns=Unicode)
    def clientVersion(ctx, strVersion):
        logger.info("QBWC: clientVersion — QBWC version %s", strVersion)
        return ''

    # ------------------------------------------------------------------
    # authenticate(username, password) → [ticket, companyFile]
    # companyFile = '' means "use the currently open QB company file"
    # ------------------------------------------------------------------
    @rpc(Unicode, Unicode, _returns=Iterable(Unicode))
    def authenticate(ctx, strUserName, strPassword):
        logger.info("QBWC: authenticate — user=%s", strUserName)
        if strUserName == config.QBWC_USERNAME and strPassword == config.QBWC_PASSWORD:
            token = str(uuid.uuid4())
            logger.info("QBWC: auth SUCCESS, token=%s", token)
            yield token
            yield ''  # '' = use currently open QB company file
        else:
            logger.warning("QBWC: auth FAILED for user=%s", strUserName)
            yield ''
            yield 'nvu'  # nvu = no valid user

    # ------------------------------------------------------------------
    # sendRequestXML(ticket, hcpResponse, companyFile, country, majorVers, minorVers) → str
    # Return qbXML string to send to QB, or '' if nothing to sync.
    # ------------------------------------------------------------------
    @rpc(Unicode, Unicode, Unicode, Unicode, Integer, Integer, _returns=Unicode)
    def sendRequestXML(ctx, ticket, strHCPResponse, strCompanyFileName,
                       qbXMLCountry, qbXMLMajorVers, qbXMLMinorVers):
        logger.info("QBWC: sendRequestXML")

        target_date = date.today() - timedelta(days=config.DEFAULT_LOOKBACK_DAYS)

        if sync_tracker.already_synced(target_date):
            logger.info("QBWC: %s already synced — returning empty", target_date)
            return ''

        try:
            sales_data  = crunchtime_client.get_sales_data(target_date)
            xml_payload = qbxml_builder.build_journal_entry_xml(sales_data)

            row_id = sync_tracker.record_attempt(
                business_date=target_date,
                status='pending',
                qbxml_sent=xml_payload,
            )
            _state['row_id']      = row_id
            _state['target_date'] = target_date

            logger.info("QBWC: sending qbXML for %s (row_id=%s)", target_date, row_id)
            return xml_payload

        except Exception as exc:
            logger.error("QBWC: error building qbXML: %s", exc, exc_info=True)
            sync_tracker.record_attempt(
                business_date=target_date,
                status='failed',
                error_message=str(exc),
            )
            return ''

    # ------------------------------------------------------------------
    # getLastError(ticket) → str
    # Called by QBWC when sendRequestXML returns '' (nothing to do).
    # Return a human-readable message explaining why we returned empty.
    # ------------------------------------------------------------------
    @rpc(Unicode, _returns=Unicode)
    def getLastError(ctx, ticket):
        logger.info("QBWC: getLastError")
        return 'No new data to sync — already up to date.'

    # ------------------------------------------------------------------
    # receiveResponseXML(ticket, response, hresult, message) → int
    # Return 100 = done, 0-99 = percent done (more requests pending),
    # negative = error.
    # ------------------------------------------------------------------
    @rpc(Unicode, Unicode, Unicode, Unicode, _returns=Integer)
    def receiveResponseXML(ctx, ticket, response, hresult, message):
        logger.info("QBWC: receiveResponseXML hresult=%s", hresult)

        row_id      = _state.get('row_id')
        target_date = _state.get('target_date')

        # Check COM-level error first (hresult is hex like '0x80040400')
        if hresult and hresult not in ('', '0x00000000'):
            error_msg = f"QB COM error hresult={hresult}: {message}"
            logger.error("QBWC: %s", error_msg)
            if row_id:
                sync_tracker.update_attempt(row_id, 'failed',
                                            qb_response=response,
                                            error_message=error_msg)
            _state['row_id'] = _state['target_date'] = None
            return -1

        # Parse the qbXML response body for application-level errors
        # QB returns statusCode="0" for success, anything else is an error
        qb_error = _parse_qbxml_error(response)
        if qb_error:
            logger.error("QBWC: qbXML error for %s: %s", target_date, qb_error)
            if row_id:
                sync_tracker.update_attempt(row_id, 'failed',
                                            qb_response=response,
                                            error_message=qb_error)
            _state['row_id'] = _state['target_date'] = None
            return -1

        logger.info("QBWC: QB accepted journal entry for %s", target_date)
        if row_id:
            sync_tracker.update_attempt(row_id, 'success', qb_response=response)

        _state['row_id'] = _state['target_date'] = None
        return 100  # 100 = done, no more requests this cycle

    # ------------------------------------------------------------------
    # closeConnection(ticket) → str
    # ------------------------------------------------------------------
    @rpc(Unicode, _returns=Unicode)
    def closeConnection(ctx, ticket):
        logger.info("QBWC: closeConnection")
        return 'Crunchtime sync complete'


def _parse_qbxml_error(response: str) -> str | None:
    """
    Parse QB's qbXML response XML and return an error string if statusCode != 0,
    or None on success.  QB embeds errors inside the response body even when the
    COM-level HRESULT is empty/zero.
    """
    if not response:
        return None
    try:
        root = ET.fromstring(response)
        # Walk every element looking for statusCode attributes
        for elem in root.iter():
            code = elem.get('statusCode')
            if code is not None and code != '0':
                severity = elem.get('statusSeverity', 'Error')
                msg      = elem.get('statusMessage', '(no message)')
                return f"QB {severity} statusCode={code}: {msg}"
    except ET.ParseError as exc:
        return f"Could not parse QB response XML: {exc}"
    return None


def create_app() -> WsgiApplication:
    """Build and return the Spyne WSGI application."""
    application = Application(
        services=[QBWebConnectorService],
        tns=QBWC_NS,
        in_protocol=Soap11(validator='lxml'),
        out_protocol=Soap11(),
    )
    return WsgiApplication(application)


if __name__ == '__main__':
    sync_tracker.initialize_db()
    app = create_app()
    logger.info(
        "SOAP server on %s:%s — WSDL: http://localhost:%s/?wsdl",
        config.SOAP_HOST, config.SOAP_PORT, config.SOAP_PORT,
    )
    if config.APP_URL == 'PLACEHOLDER':
        logger.warning("APP_URL is still PLACEHOLDER — run ngrok and update config.py!")
    server = make_server(config.SOAP_HOST, config.SOAP_PORT, app)
    server.serve_forever()
