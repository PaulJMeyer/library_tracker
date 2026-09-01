import time
from urllib.parse import urljoin

import requests


BASE_URL = "https://opac.stabi-hb.de"
REQUEST_TIMEOUT = 10
REQUEST_DELAY = 1.0


def build_url(path: str) -> str:
    return urljoin(BASE_URL, path)


def get(session: requests.Session, url: str, *, params: dict[str, str] | None = None,
        delay: bool = True) -> requests.Response:
    
    if delay:
        time.sleep(REQUEST_DELAY)

    response = session.get(url, params=params, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response


def post(session: requests.Session, url: str, data: dict, *, delay: bool = True) -> requests.Response:
    if delay:
        time.sleep(REQUEST_DELAY)

    response = session.post(url, data=data, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response