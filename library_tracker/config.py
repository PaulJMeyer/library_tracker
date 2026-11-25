from __future__ import annotations

import os

from dotenv import load_dotenv

from library_tracker.models import ReadoListType


load_dotenv()

LIBRARY_BASE_URL = "https://opac.stabi-hb.de"
READO_BASE_URL = "https://reado.app"

READO_LIST_TYPES: tuple[ReadoListType, ...] = (
    "wishlist",
    "tbr",
    "reading",
    "completed",
    "abandoned",
)
# READO lists whose books are done with: they are removed from the library Merkliste.
FINISHED_LIST_TYPES: tuple[ReadoListType, ...] = ("tbr", "reading", "completed", "abandoned")

READO_LIST_LABELS: dict[ReadoListType, str] = {
    "wishlist": "Wunschliste",
    "tbr": "Stapel ungelesener Bücher",
    "reading": "Am Lesen/Hören",
    "completed": "Abgeschlossen",
    "abandoned": "Abgebrochen",
}

READO_LIST_ENV_VARS: dict[ReadoListType, str] = {
    "wishlist": "READO_WISHLIST_URL",
    "tbr": "READO_TBR_URL",
    "reading": "READO_READING_URL",
    "completed": "READO_COMPLETED_URL",
    "abandoned": "READO_ABANDONED_URL",
}


class ConfigurationError(RuntimeError):
    """Raised when required local or CI configuration is missing."""


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ConfigurationError(f"{name} is not configured.")
    return value


def configured_reado_list_types() -> tuple[ReadoListType, ...]:
    """The wishlist plus every other READO list that has a URL configured."""
    configured: list[ReadoListType] = ["wishlist"]
    configured.extend(
        list_type
        for list_type in READO_LIST_TYPES
        if list_type != "wishlist" and os.getenv(READO_LIST_ENV_VARS[list_type])
    )
    return tuple(configured)


def get_reado_list_url(list_type: ReadoListType) -> str:
    return require_env(READO_LIST_ENV_VARS[list_type])


TELEGRAM_TOKEN_ENV_VAR = "TELEGRAM_BOT_TOKEN"
TELEGRAM_CHAT_ID_ENV_VAR = "TELEGRAM_CHAT_ID"


def get_telegram_settings() -> tuple[str, str]:
    return require_env(TELEGRAM_TOKEN_ENV_VAR), require_env(TELEGRAM_CHAT_ID_ENV_VAR)
