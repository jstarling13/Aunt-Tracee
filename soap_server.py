# =============================================================================
# soap_server.py — QBWC SOAP server, multi-store edition (13 Canyon Donuts)
# =============================================================================
# QBWC calls these 6 methods in sequence each sync cycle:
#   1. serverVersion      — version handshake
#   2. clientVersion      — version handshake
#   3. authenticate       — credential check, returns session ticket
#   4. sendRequestXML     — we return qbXML; QB processes it
#   5. receiveResponseXML — QB returns result; we log it
#   6. closeConnection    — cycle complete
#
# Multi-store routing:
#   Each store has its own .qwc file loaded in QBWC.
#   When QBWC calls sendRequestXML it passes strCompanyFileName — the path
#   to the QB company file it currently has open. We match that path against
#   config.LOCATIONS to find which store we're syncing, then fetch that
#   store's sales data and build its journal entry.
#
#   On-site: once qb_file paths are filled in config.py, routing is automatic.
#   Until then: falls back to the first PLACEHOLDER-free location found.
# =============================================================================

import logging
import os
import uuid
import xml.etree.ElementTree as ET
from datetime import date

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

# Session state — one sync cycle at a time
_state = {
    'row_id':      None,
    'week_start':  None,
    'week_end':    None,
    'location':    None,
}

QBWC_NS = 'http://developer.intuit.com/'


# ---------------------------------------------------------------------------
# Store lookup helpers
# ---------------------------------------------------------------------------

def _find_location_by_qb_file(company_file: str) -> dict | None:
    """
    Match the QB company file path QBWC sends us to a location in config.
    Tries exact match first, then basename match (in case paths differ slightly).
    """
    if not company_file:
        return None
    company_file_lower = company_file.lower().replace('\\', '/')
    basename = os.path.basename(company_file_lower)

    for loc in config.LOCATIONS:
        qb = loc.get('qb_file', '')
        if not qb or qb == 'PLACEHOLDER':
            continue
        qb_lower = qb.lower().replace('\\', '/')
        if company_file_lower == qb_lower:
            return loc
        if basename and basename == os.path.basename(qb_lower):
            return loc
    return None


def _find_location_by_id(location_id: str) -> dict | None:
    """Look up a location by Crunchtime ID."""
    for loc in config.LOCATIONS:
        if loc['crunchtime_id'] == location_id:
            return loc
    return None


def _pick_location(company_file: str) -> dict | None:
    """
    Pick the right location for this sync cycle.
    1. Try matching on QB company file path (production — paths filled in)
    2. Fall back to first location with a non-PLACEHOLDER qb_file
    3. Last resort: first location in list (mock/dev mode)
    """
    loc = _find_location_by_qb_file(company_file)
    if loc:
        return loc

    # Paths not filled in yet — use first available location
    for loc in config.LOCATIONS:
        if loc.get('qb_file', 'PLACEHOLDER') != 'PLACEHOLDER':
            logger.warning(
                "Company file '%s' not matched — defaulting to %s",
                company_file, loc['name']
            )
            return loc

    # Dev/mock mode — just use first location
    loc = config.LOCATIONS[0]
    logger.warning("No QB file paths configured — using %s for mock sync", loc['name'])
    return loc


# ---------------------------------------------------------------------------
# SOAP service
# ---------------------------------------------------------------------------

class QBWebConnectorService(ServiceBase):

    @rpc(Unicode, _returns=Unicode)
    def serverVersion(ctx, ticket):
        logger.info("QBWC: serverVersion")
        return '1.0.0'

    @rpc(Unicode, _returns=Unicode)
    def clientVersion(ctx, strVersion):
        logger.info("QBWC: clientVersion — %s", strVersion)
        return ''

    @rpc(Unicode, Unicode, _returns=Iterable(Unicode))
    def authenticate(ctx, strUserName, strPassword):
        logger.info("QBWC: authenticate — user=%s", strUserName)
        if strUserName == config.QBWC_USERNAME and strPassword == config.QBWC_PASSWORD:
            token = str(uuid.uuid4())
            logger.info("QBWC: auth SUCCESS token=%s", token)
            yield token
            yield ''   # '' = use currently open QB company file
        else:
            logger.warning("QBWC: auth FAILED for user=%s", strUserName)
            yield ''
            yield 'nvu'

    @rpc(Unicode, Unicode, Unicode, Unicode, Integer, Integer, _returns=Unicode)
    def sendRequestXML(ctx, ticket, strHCPResponse, strCompanyFileName,
                       qbXMLCountry, qbXMLMajorVers, qbXMLMinorVers):
        logger.info("QBWC: sendRequestXML — company_file=%s", strCompanyFileName)

        # Identify which store this sync is for
        location = _pick_location(strCompanyFileName)
        if not location:
            logger.error("QBWC: could not identify store — aborting")
            return ''

        # Calculate the week we're syncing (most recent completed Sun-Sat week)
        week_start, week_end = qbxml_builder.get_week_range()

        # Duplicate guard — skip if this store+week is already successfully synced
        if sync_tracker.already_synced(location['crunchtime_id'], week_start):
            logger.info("QBWC: %s week %s already synced — returning empty",
                        location['name'], week_start)
            _state['location'] = None
            return ''

        try:
            sales_data  = crunchtime_client.get_weekly_sales(location, week_start, week_end)
            xml_payload = qbxml_builder.build_weekly_journal_entry_xml(sales_data, location)

            row_id = sync_tracker.record_attempt(
                location_id   = location['crunchtime_id'],
                store_name    = location['name'],
                week_start    = week_start,
                week_end      = week_end,
                status        = 'pending',
                qbxml_sent    = xml_payload,
            )
            _state['row_id']     = row_id
            _state['week_start'] = week_start
            _state['week_end']   = week_end
            _state['location']   = location

            logger.info("QBWC: sending qbXML for %s week %s (row_id=%s)",
                        location['name'], week_start, row_id)
            return xml_payload

        except Exception as exc:
            logger.error("QBWC: error building qbXML for %s: %s",
                         location['name'], exc, exc_info=True)
            sync_tracker.record_attempt(
                location_id   = location['crunchtime_id'],
                store_name    = location['name'],
                week_start    = week_start,
                week_end      = week_end,
                status        = 'failed',
                error_message = str(exc),
            )
            return ''

    @rpc(Unicode, _returns=Unicode)
    def getLastError(ctx, ticket):
        logger.info("QBWC: getLastError")
        loc = _state.get('location')
        if loc:
            return f"No new data to sync for {loc['name']} — already up to date."
        return 'No new data to sync — already up to date.'

    @rpc(Unicode, Unicode, Unicode, Unicode, _returns=Integer)
    def receiveResponseXML(ctx, ticket, response, hresult, message):
        logger.info("QBWC: receiveResponseXML hresult=%s", hresult)

        row_id   = _state.get('row_id')
        location = _state.get('location')
        week     = _state.get('week_start')

        # COM-level error
        if hresult and hresult not in ('', '0x00000000'):
            error_msg = f"QB COM error hresult={hresult}: {message}"
            logger.error("QBWC: %s", error_msg)
            if row_id:
                sync_tracker.update_attempt(row_id, 'failed',
                                            qb_response=response,
                                            error_message=error_msg)
            _clear_state()
            return -1

        # Application-level error inside the qbXML response
        qb_error = _parse_qbxml_error(response)
        if qb_error:
            store = location['name'] if location else 'unknown'
            logger.error("QBWC: qbXML error for %s week %s: %s", store, week, qb_error)
            if row_id:
                sync_tracker.update_attempt(row_id, 'failed',
                                            qb_response=response,
                                            error_message=qb_error)
            _clear_state()
            return -1

        store = location['name'] if location else 'unknown'
        logger.info("QBWC: QB accepted journal entry for %s week %s", store, week)
        if row_id:
            sync_tracker.update_attempt(row_id, 'success', qb_response=response)

        _clear_state()
        return 100

    @rpc(Unicode, _returns=Unicode)
    def closeConnection(ctx, ticket):
        logger.info("QBWC: closeConnection")
        return 'Crunchtime sync complete'


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clear_state():
    _state['row_id'] = _state['week_start'] = _state['week_end'] = _state['location'] = None


def _parse_qbxml_error(response: str) -> str | None:
    """Parse QB response XML for application-level errors (statusCode != 0)."""
    if not response:
        return None
    try:
        root = ET.fromstring(response)
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
    logger.info("SOAP server on %s:%s — WSDL: http://localhost:%s/?wsdl",
                config.SOAP_HOST, config.SOAP_PORT, config.SOAP_PORT)
    server = make_server(config.SOAP_HOST, config.SOAP_PORT, app)
    server.serve_forever()
