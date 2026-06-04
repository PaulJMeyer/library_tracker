import os
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

LOGIN_PAGE_URL = "https://opac.stabi-hb.de/webOPACClient/start.do?StartPage=UserAccount"
LOGIN_URL = "https://opac.stabi-hb.de/webOPACClient/login.do"


def get_login_page(session):
    response = session.get(LOGIN_PAGE_URL)
    response.raise_for_status()
    return response


def extract_login_payload(html):
    soup = BeautifulSoup(html, "html.parser")

    csid_input = soup.find("input", {"name": "CSId"})
    if csid_input is None:
        raise ValueError("CSId wurde nicht gefunden.")

    return {
        "methodToCall": "submit",
        "CSId": csid_input["value"],
        "username": os.getenv("LIBRARY_USERNAME"),
        "password": os.getenv("LIBRARY_PASSWORD"),
        "login_action": "Login",
    }


def login():
    load_dotenv()

    session = requests.Session()

    login_page = get_login_page(session)
    payload = extract_login_payload(login_page.text)

    response = session.post(LOGIN_URL, data=payload)
    response.raise_for_status()

    if "methodToCall=logout" not in response.text:
        raise ValueError("Login wahrscheinlich fehlgeschlagen.")

    print("Login erfolgreich.")

    return session