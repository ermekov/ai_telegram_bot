import logging

from app.sheets import GoogleSheetsClient
from app.storage import SQLiteStorage


logger = logging.getLogger(__name__)


async def sync_unsynced_leads(
    storage: SQLiteStorage,
    sheets: GoogleSheetsClient,
) -> int:
    synced = 0
    for lead in storage.get_unsynced_leads():
        logger.info("Syncing lead %s to Google Sheets", lead.id)
        result = await sheets.append_lead(
            name=lead.name,
            phone=lead.phone,
            telegram_id=lead.chat_id,
        )
        storage.mark_lead_sheets_synced(lead.id)
        synced += 1
        if result:
            logger.info(
                "Lead %s synced to Google Sheets: %s / %s / %s",
                lead.id,
                result.spreadsheet_title,
                result.worksheet_title,
                result.updated_range,
            )
        else:
            logger.info("Lead %s marked synced locally; Google Sheets is disabled", lead.id)
    return synced
