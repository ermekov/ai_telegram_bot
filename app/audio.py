import asyncio
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from aiogram import Bot


class VoiceTranscriptionError(RuntimeError):
    """Raised when a Telegram voice message cannot be prepared for transcription."""


async def download_voice_as_mp3(bot: Bot, file_id: str) -> Path:
    fd, source_name = tempfile.mkstemp(suffix=".ogg")
    os.close(fd)
    source_path = Path(source_name)
    target_path = source_path.with_suffix(".mp3")

    try:
        file = await bot.get_file(file_id)
        await bot.download_file(file.file_path, destination=source_path)
        await asyncio.to_thread(_convert_to_mp3, source_path, target_path)
        return target_path
    except VoiceTranscriptionError:
        target_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        target_path.unlink(missing_ok=True)
        raise VoiceTranscriptionError(
            "Не смог подготовить голосовое сообщение. Попробуйте отправить текстом."
        ) from exc
    finally:
        source_path.unlink(missing_ok=True)


def _convert_to_mp3(source_path: Path, target_path: Path) -> None:
    if shutil.which("ffmpeg") is None:
        raise VoiceTranscriptionError(
            "Для голосовых сообщений нужен FFmpeg. Установите FFmpeg и добавьте его в PATH."
        )

    command = [
        "ffmpeg",
        "-y",
        "-i",
        str(source_path),
        "-vn",
        "-ar",
        "16000",
        "-ac",
        "1",
        "-b:a",
        "64k",
        str(target_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise VoiceTranscriptionError(
            "Не смог конвертировать голосовое сообщение. Проверьте установку FFmpeg."
        )
