from __future__ import annotations

import requests

TELEGRAM_API_URL = "https://api.telegram.org/bot{token}/sendMessage"
TELEGRAM_MAX_MESSAGE_LENGTH = 4096
REQUEST_TIMEOUT = 15


class TelegramError(RuntimeError):
    """Raised when a Telegram message cannot be delivered."""


def split_message(text: str, limit: int = TELEGRAM_MAX_MESSAGE_LENGTH) -> list[str]:
    """Split text at line breaks into chunks that fit Telegram's length limit."""
    chunks: list[str] = []
    current = ""
    for line in text.split("\n"):
        while len(line) > limit:
            if current:
                chunks.append(current)
                current = ""
            chunks.append(line[:limit])
            line = line[limit:]
        candidate = f"{current}\n{line}" if current else line
        if len(candidate) > limit:
            chunks.append(current)
            current = line
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks


class TelegramClient:
    def __init__(
        self,
        token: str,
        chat_id: str,
        session: requests.Session | None = None,
    ) -> None:
        self.token = token
        self.chat_id = chat_id
        self.session = session or requests.Session()

    def send_message(self, text: str) -> None:
        url = TELEGRAM_API_URL.format(token=self.token)
        for chunk in split_message(text):
            try:
                response = self.session.post(
                    url,
                    data={
                        "chat_id": self.chat_id,
                        "text": chunk,
                        "parse_mode": "HTML",
                        "disable_web_page_preview": "true",
                    },
                    timeout=REQUEST_TIMEOUT,
                )
            except requests.RequestException as exc:
                # Never include the URL: it contains the bot token.
                raise TelegramError(
                    f"Telegram request failed: {type(exc).__name__}"
                ) from None

            if response.status_code != 200:
                description = ""
                try:
                    description = str(response.json().get("description", ""))
                except ValueError:
                    pass
                raise TelegramError(
                    f"Telegram rejected the message (HTTP {response.status_code}) {description}".strip()
                )
