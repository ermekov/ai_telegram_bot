import asyncio
import logging

from app.config import SettingsError, load_settings
from app.sheets import GoogleSheetsClient
from app.storage import SQLiteStorage
from app.sync import sync_unsynced_leads


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        settings = load_settings()
    except SettingsError as exc:
        print(exc)
        return

    storage = SQLiteStorage(settings.database_path)
    storage.init()
    sheets = GoogleSheetsClient(settings)

    count = await sync_unsynced_leads(storage, sheets)
    print(f"Synced leads: {count}")


if __name__ == "__main__":
    asyncio.run(main())
