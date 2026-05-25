# =============================================================================
# qwc_generator.py — Auto-generates one .qwc file per store
# =============================================================================
# Run: python main.py generate-qwc
#
# Output: qwc_files/CT_Sync_{location_id}.qwc  (one per store)
#
# Each .qwc file is loaded into QuickBooks Web Connector once per store.
# QBWC then opens the right QB company file and calls the SOAP server weekly.
# =============================================================================

import os
import uuid
import logging

import config

logger = logging.getLogger(__name__)

QWC_DIR = 'qwc_files'


def generate_all():
    """Generate one .qwc file for every store in config.LOCATIONS."""
    os.makedirs(QWC_DIR, exist_ok=True)
    generated = []

    for loc in config.LOCATIONS:
        path = _generate_one(loc)
        generated.append((loc['name'], path))
        logger.info("Generated: %s", path)

    return generated


def _generate_one(location: dict) -> str:
    """
    Write a .qwc file for one store and return the file path.

    OwnerID and FileID are generated deterministically from the location ID
    using uuid5 — so they're always the same for the same store, and unique
    across stores.
    """
    loc_id     = location['crunchtime_id']
    store_name = location['name']
    qb_file    = location.get('qb_file', '')

    # Deterministic UUIDs — same store always gets same IDs
    namespace  = uuid.UUID('57F3B9D1-2A4C-4E8F-B1C7-9D3E6A0F5B82')
    owner_id   = str(uuid.uuid5(namespace, f"owner-{loc_id}")).upper()
    file_id    = str(uuid.uuid5(namespace, f"file-{loc_id}")).upper()

    # MinutesToPoll: 10080 = 7 days (weekly sync)
    # QBWC will check every 10080 minutes — effectively once a week
    minutes_to_poll = 10080

    # If QB file path is known, include it so QBWC opens the right company file
    # If PLACEHOLDER, leave it out and QBWC will use whichever file is open
    file_tag = ''
    if qb_file and qb_file != 'PLACEHOLDER':
        file_tag = f'\n  <QBFile>{qb_file}</QBFile>'

    xml = f'''<?xml version="1.0"?>
<QBWCXML>
  <AppName>Crunchtime Sync - {store_name}</AppName>
  <AppID>CT_Sync_{loc_id}</AppID>
  <AppURL>{config.APP_URL}/soap</AppURL>
  <AppSupport>{config.APP_URL}</AppSupport>
  <AppDescription>Weekly Crunchtime sales sync for {store_name}</AppDescription>
  <UserName>{config.QBWC_USERNAME}</UserName>
  <OwnerID>{{{owner_id}}}</OwnerID>
  <FileID>{{{file_id}}}</FileID>
  <MinutesToPoll>{minutes_to_poll}</MinutesToPoll>
  <QBType>QBFS</QBType>
  <IsReadOnly>false</IsReadOnly>{file_tag}
</QBWCXML>'''

    filename = f"CT_Sync_{loc_id}_{store_name.replace(' ', '_').replace(',', '')}.qwc"
    filepath = os.path.join(QWC_DIR, filename)

    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(xml)

    return filepath
