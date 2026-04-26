import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from aiogram.utils.chat_action import ChatActionSender

from app.audio import VoiceTranscriptionError, download_voice_as_mp3
from app.config import SettingsError, load_settings
from app.leads import extract_lead_update, looks_like_order_intent
from app.openai_service import OpenAIService
from app.prompts import FIRST_MESSAGE
from app.sheets import GoogleSheetsClient
from app.storage import SQLiteStorage
from app.sync import sync_unsynced_leads


logger = logging.getLogger(__name__)


async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    try:
        settings = load_settings()
    except SettingsError as exc:
        logger.error("%s", exc)
        return

    storage = SQLiteStorage(settings.database_path)
    storage.init()

    ai = OpenAIService(settings)
    sheets = GoogleSheetsClient(settings)

    bot = Bot(token=settings.telegram_bot_token)
    dp = Dispatcher()

    @dp.message(CommandStart())
    async def handle_start(message: Message) -> None:
        await message.answer(FIRST_MESSAGE)

    @dp.message(Command("reset"))
    async def handle_reset(message: Message) -> None:
        storage.clear_chat(str(message.chat.id))
        await message.answer("Готово ✅ Память этого диалога очищена.")

    @dp.message(Command("sync_sheets"))
    async def handle_sync_sheets(message: Message) -> None:
        try:
            count = await sync_unsynced_leads(storage, sheets)
        except Exception:
            logger.exception("Google Sheets sync failed")
            await message.answer(
                "Не получилось отправить заявки в Google Sheets. Проверьте доступ к таблице и terminal logs."
            )
            return

        await message.answer(f"Готово ✅ Отправлено заявок в Google Sheets: {count}")

    @dp.message(Command("check_sheets"))
    async def handle_check_sheets(message: Message) -> None:
        try:
            info = await sheets.inspect()
        except Exception:
            logger.exception("Google Sheets check failed")
            await message.answer(
                "Не получилось проверить Google Sheets. Посмотрите ошибку в terminal logs."
            )
            return

        last_rows = info["last_rows"][-3:]
        preview = "\n".join(str(row) for row in last_rows) or "пусто"
        await message.answer(
            "Google Sheets подключён ✅\n"
            f"Таблица: {info['spreadsheet_title']}\n"
            f"Лист: {info['worksheet_title']}\n"
            f"Строк с данными: {info['row_count']}\n"
            f"Последние строки:\n{preview}"
        )

    @dp.message(F.contact)
    async def handle_contact(message: Message) -> None:
        contact = message.contact
        name = " ".join(
            part for part in [contact.first_name, contact.last_name] if part
        ).strip()
        phone = contact.phone_number

        reply = await process_lead(
            message=message,
            storage=storage,
            sheets=sheets,
            text="",
            forced_name=name or None,
            forced_phone=phone,
        )
        await message.answer(reply or "Спасибо! ✅ Ваша заявка принята.")

    @dp.message(F.voice)
    async def handle_voice(message: Message, bot: Bot) -> None:
        try:
            async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
                mp3_path = await download_voice_as_mp3(bot, message.voice.file_id)
                try:
                    user_text = await ai.transcribe_audio(mp3_path)
                finally:
                    mp3_path.unlink(missing_ok=True)
        except VoiceTranscriptionError as exc:
            await message.answer(str(exc))
            return
        except Exception:
            logger.exception("Voice processing failed")
            await message.answer(
                "Не смог обработать голосовое сообщение. Попробуйте отправить текстом."
            )
            return

        if not user_text:
            await message.answer("Не удалось распознать голосовое. Попробуйте ещё раз.")
            return

        await handle_user_text(
            message, bot, storage, ai, sheets, user_text, settings.context_window
        )

    @dp.message(F.text)
    async def handle_text(message: Message, bot: Bot) -> None:
        await handle_user_text(
            message, bot, storage, ai, sheets, message.text or "", settings.context_window
        )

    @dp.message()
    async def handle_unknown(message: Message) -> None:
        await message.answer(
            "Пока я умею работать с текстом, контактами и голосовыми сообщениями."
        )

    await bot.delete_webhook(drop_pending_updates=True)
    logger.info("Bot started")
    await dp.start_polling(bot)


async def handle_user_text(
    message: Message,
    bot: Bot,
    storage: SQLiteStorage,
    ai: OpenAIService,
    sheets: GoogleSheetsClient,
    user_text: str,
    context_window: int,
) -> None:
    chat_id = str(message.chat.id)
    user_text = user_text.strip()

    if not user_text:
        await message.answer("Отправьте, пожалуйста, текстовое сообщение.")
        return

    order_intent = looks_like_order_intent(user_text)
    if order_intent:
        storage.start_new_lead_draft(chat_id)

    lead_reply = None
    if not order_intent or _contains_contact_data(user_text):
        lead_reply = await process_lead(
            message=message,
            storage=storage,
            sheets=sheets,
            text=user_text,
        )
        if lead_reply:
            storage.add_message(chat_id, "user", user_text)
            storage.add_message(chat_id, "assistant", lead_reply)
            await message.answer(lead_reply)
            return

    if order_intent:
        reply = (
            "Отлично! 🙌\n"
            "Чтобы оформить заявку, пожалуйста, отправьте:\n\n"
            "• Ваше имя\n"
            "• Номер телефона (WhatsApp или Telegram)"
        )
        storage.add_message(chat_id, "user", user_text)
        storage.add_message(chat_id, "assistant", reply)
        await message.answer(reply)
        return

    history = storage.get_recent_messages(chat_id, limit=context_window)

    try:
        async with ChatActionSender.typing(bot=bot, chat_id=message.chat.id):
            answer = await ai.generate_reply(history=history, user_text=user_text)
    except Exception:
        logger.exception("OpenAI response failed")
        await message.answer(
            "Сейчас не получилось получить ответ от AI. Попробуйте ещё раз чуть позже."
        )
        return

    storage.add_message(chat_id, "user", user_text)
    storage.add_message(chat_id, "assistant", answer)
    await message.answer(answer)


def _contains_contact_data(text: str) -> bool:
    return any(char.isdigit() for char in text)


async def process_lead(
    message: Message,
    storage: SQLiteStorage,
    sheets: GoogleSheetsClient,
    text: str,
    forced_name: str | None = None,
    forced_phone: str | None = None,
) -> str | None:
    chat_id = str(message.chat.id)
    current = storage.get_lead_draft(chat_id)
    current_was_saved = bool(current and current.saved_at)
    update = extract_lead_update(
        text=text,
        current_name=None if current_was_saved else (current.name if current else None),
        current_phone=None if current_was_saved else (current.phone if current else None),
        draft_exists=current is not None,
        forced_name=forced_name,
        forced_phone=forced_phone,
    )

    if not update.has_changes:
        return None

    if current_was_saved:
        storage.start_new_lead_draft(chat_id)

    storage.upsert_lead_draft(chat_id, name=update.name, phone=update.phone)
    draft = storage.get_lead_draft(chat_id)
    if not draft:
        return None

    if draft.name and draft.phone and not draft.saved_at:
        username = message.from_user.username if message.from_user else None
        logger.info(
            "Saving lead for chat %s: name=%s phone=%s",
            chat_id,
            draft.name,
            draft.phone,
        )
        lead_id = storage.save_lead(
            chat_id=chat_id,
            username=username,
            name=draft.name,
            phone=draft.phone,
        )
        storage.mark_lead_saved(chat_id)

        try:
            logger.info("Sending lead %s to Google Sheets", lead_id)
            result = await sheets.append_lead(
                name=draft.name,
                phone=draft.phone,
                telegram_id=chat_id,
            )
            storage.mark_lead_sheets_synced(lead_id)
            if result:
                logger.info(
                    "Lead %s sent to Google Sheets: %s / %s / %s",
                    lead_id,
                    result.spreadsheet_title,
                    result.worksheet_title,
                    result.updated_range,
                )
            else:
                logger.info("Lead %s saved locally; Google Sheets is disabled", lead_id)
        except Exception:
            logger.exception("Google Sheets append failed")

        return (
            "Спасибо! ✅\n"
            "Ваша заявка принята.\n"
            "Наш менеджер свяжется с вами в ближайшее время 😊"
        )

    if draft.name and not draft.phone:
        return (
            "Спасибо! 😊\n"
            "Подскажите, пожалуйста, ещё номер телефона, чтобы мы могли с вами связаться."
        )

    if draft.phone and not draft.name:
        return (
            "Спасибо! 😊\n"
            "Подскажите, пожалуйста, ещё ваше имя, чтобы мы могли оформить заявку."
        )

    return None


if __name__ == "__main__":
    asyncio.run(main())
