import os
from bs4 import BeautifulSoup, Tag
from client import build_url, get, post
from requests import Session, Response

LOGIN_PAGE_URL = build_url("/webOPACClient/start.do?StartPage=UserAccount")
LOGIN_URL = build_url("/webOPACClient/login.do")


def get_login_page(session: Session) -> Response:
    return get(session, LOGIN_PAGE_URL, delay=False)


def extract_login_payload(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")

    csid_input = soup.find("input", {"name": "CSId"})
    if not isinstance(csid_input, Tag):
        raise ValueError("CSId wurde nicht gefunden.")

    return {
        "methodToCall": "submit",
        "CSId": csid_input["value"],
        "username": os.getenv("LIBRARY_USERNAME"),
        "password": os.getenv("LIBRARY_PASSWORD"),
        "login_action": "Login",
    }


def login() -> Session:

    session = Session()

    login_page = get_login_page(session)
    payload = extract_login_payload(login_page.text)

    response = post(session, LOGIN_URL, data=payload, delay=False)
    response.raise_for_status()

    if "methodToCall=logout" not in response.text:
        raise ValueError("Login wahrscheinlich fehlgeschlagen.")

    print("Login erfolgreich.")

    return session