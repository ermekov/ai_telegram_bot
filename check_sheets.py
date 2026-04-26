import asyncio
import logging

from app.config import SettingsError, load_settings
from app.sheets import GoogleSheetsClient


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

    sheets = GoogleSheetsClient(settings)
    info = await sheets.inspect()

    print(f"Spreadsheet: {info['spreadsheet_title']}")
    print(f"Spreadsheet ID: {info['spreadsheet_id']}")
    print(f"Target worksheet: {info['worksheet_title']}")
    print(f"All worksheets: {info['worksheet_names']}")
    print(f"Rows with values: {info['row_count']}")
    print("Last rows:")
    for row in info["last_rows"]:
        print(row)


if __name__ == "__main__":
    asyncio.run(main())
