import asyncio
from dataclasses import dataclass

from app.config import Settings


@dataclass(frozen=True)
class SheetAppendResult:
    spreadsheet_title: str
    worksheet_title: str
    updated_range: str


class GoogleSheetsClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def append_lead(
        self, name: str, phone: str, telegram_id: str
    ) -> SheetAppendResult | None:
        if not self._settings.google_sheets_enabled:
            return None

        return await asyncio.to_thread(
            self._append_lead_sync, name, phone, telegram_id
        )

    async def inspect(self) -> dict[str, object]:
        return await asyncio.to_thread(self._inspect_sync)

    def _append_lead_sync(
        self, name: str, phone: str, telegram_id: str
    ) -> SheetAppendResult:
        if not self._settings.google_sheets_spreadsheet_id:
            raise RuntimeError("GOOGLE_SHEETS_SPREADSHEET_ID is empty")
        if not self._settings.google_sheets_credentials_file.exists():
            raise RuntimeError("Google Sheets credentials file does not exist")

        import gspread

        client = gspread.service_account(
            filename=str(self._settings.google_sheets_credentials_file)
        )
        spreadsheet = client.open_by_key(self._settings.google_sheets_spreadsheet_id)
        worksheet = spreadsheet.worksheet(self._settings.google_sheets_worksheet)
        next_row = self._find_next_row(worksheet)
        response = worksheet.update(
            f"A{next_row}:C{next_row}",
            [[name, phone, telegram_id]],
            value_input_option="USER_ENTERED",
            include_values_in_response=True,
        )
        updated_range = response.get("updatedRange", f"A{next_row}:C{next_row}")
        return SheetAppendResult(
            spreadsheet_title=spreadsheet.title,
            worksheet_title=worksheet.title,
            updated_range=updated_range,
        )

    def _inspect_sync(self) -> dict[str, object]:
        if not self._settings.google_sheets_spreadsheet_id:
            raise RuntimeError("GOOGLE_SHEETS_SPREADSHEET_ID is empty")
        if not self._settings.google_sheets_credentials_file.exists():
            raise RuntimeError("Google Sheets credentials file does not exist")

        import gspread

        client = gspread.service_account(
            filename=str(self._settings.google_sheets_credentials_file)
        )
        spreadsheet = client.open_by_key(self._settings.google_sheets_spreadsheet_id)
        worksheet = spreadsheet.worksheet(self._settings.google_sheets_worksheet)
        values = worksheet.get_all_values()
        return {
            "spreadsheet_title": spreadsheet.title,
            "spreadsheet_id": self._settings.google_sheets_spreadsheet_id,
            "worksheet_title": worksheet.title,
            "worksheet_names": [item.title for item in spreadsheet.worksheets()],
            "row_count": len(values),
            "last_rows": values[-10:],
        }

    @staticmethod
    def _find_next_row(worksheet) -> int:
        values = worksheet.get("A:C")
        last_filled_row = 0
        for index, row in enumerate(values, start=1):
            if any(str(cell).strip() for cell in row):
                last_filled_row = index
        return last_filled_row + 1
