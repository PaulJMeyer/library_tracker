import requests

LOGIN_PAGE_URL = "https://opac.stabi-hb.de/webOPACClient/start.do?Login=0"


def get_login_page():
    session = requests.Session()

    response = session.get(LOGIN_PAGE_URL)

    print(f"Status: {response.status_code}")
    print(f"URL: {response.url}")

    return session, response