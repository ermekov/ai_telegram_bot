import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent


class SettingsError(RuntimeError):
    """Raised when required environment variables are missing."""


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    openai_api_key: str
    openai_chat_model: str
    openai_transcribe_model: str
    database_path: Path
    context_window: int
    google_sheets_enabled: bool
    google_sheets_credentials_file: Path
    google_sheets_spreadsheet_id: str
    google_sheets_worksheet: str


def load_settings() -> Settings:
    load_dotenv(BASE_DIR / ".env")

    telegram_bot_token = _required("TELEGRAM_BOT_TOKEN")
    openai_api_key = _required("OPENAI_API_KEY")

    return Settings(
        telegram_bot_token=telegram_bot_token,
        openai_api_key=openai_api_key,
        openai_chat_model=os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1"),
        openai_transcribe_model=os.getenv(
            "OPENAI_TRANSCRIBE_MODEL", "gpt-4o-mini-transcribe"
        ),
        database_path=_path(os.getenv("DATABASE_PATH", "data/bot.sqlite3")),
        context_window=int(os.getenv("CONTEXT_WINDOW", "20")),
        google_sheets_enabled=_bool(os.getenv("GOOGLE_SHEETS_ENABLED", "false")),
        google_sheets_credentials_file=_path(
            os.getenv("GOOGLE_SHEETS_CREDENTIALS_FILE", "service_account.json")
        ),
        google_sheets_spreadsheet_id=os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID", ""),
        google_sheets_worksheet=os.getenv("GOOGLE_SHEETS_WORKSHEET", "Лист1"),
    )


def _required(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise SettingsError(f"Заполните переменную {name} в telegram_ai_bot/.env")
    return value


def _bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _path(value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = BASE_DIR / path
    return path
