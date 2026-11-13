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
)

READO_LIST_ENV_VARS: dict[ReadoListType, str] = {
    "wishlist": "READO_WISHLIST_URL",
    "tbr": "READO_TBR_URL",
    "reading": "READO_READING_URL",
    "completed": "READO_COMPLETED_URL",
}


class ConfigurationError(RuntimeError):
    """Raised when required local or CI configuration is missing."""


def require_env(name: str) -> str:
    value = os.getenv(name)
    if not value:
        raise ConfigurationError(f"{name} is not configured.")
    return value


def get_reado_list_url(list_type: ReadoListType) -> str:
    return require_env(READO_LIST_ENV_VARS[list_type])
