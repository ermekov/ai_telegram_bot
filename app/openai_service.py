from pathlib import Path

from openai import AsyncOpenAI

from app.config import Settings
from app.prompts import SYSTEM_PROMPT


class OpenAIService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def generate_reply(self, history: list[dict[str, str]], user_text: str) -> str:
        messages = [
            {"role": item["role"], "content": item["content"]}
            for item in history
            if item["role"] in {"user", "assistant"} and item["content"]
        ]
        messages.append({"role": "user", "content": user_text})

        response = await self._client.responses.create(
            model=self._settings.openai_chat_model,
            instructions=SYSTEM_PROMPT,
            input=messages,
        )
        return (response.output_text or "").strip()

    async def transcribe_audio(self, audio_path: Path) -> str:
        with audio_path.open("rb") as audio_file:
            transcript = await self._client.audio.transcriptions.create(
                model=self._settings.openai_transcribe_model,
                file=audio_file,
            )
        return (transcript.text or "").strip()
