import pytest

from pages.login_page import LoginPage
from utils.data_loader import load_json


def load_test_data():
    """Login scenarios from test_data/login_data.json.

    Credentials in that file are ${PLACEHOLDER} tokens resolved from the
    environment by utils.data_loader, so no password literal lives in a test.
    """
    return load_json("login_data.json")


LOGIN_DATA = load_test_data()


@pytest.mark.ui
@pytest.mark.smoke
@pytest.mark.regression
@pytest.mark.parametrize("data", LOGIN_DATA, ids=[case["id"] for case in LOGIN_DATA])
def test_login(browser_page, data):

    page = browser_page

    login_page = LoginPage(page)

    username = data["username"]
    password = data["password"]
    expected = data["expected"]

    login_page.login(username, password)

    if expected == "success":

        assert "inventory.html" in page.url

    elif expected == "locked":

        error = login_page.get_error_message()

        assert "locked out" in error.lower(), "Locked user was able to login or wrong error message shown"

    elif expected == "fail":

        error = login_page.get_error_message()

        assert error is not None, "Error message not displayed for invalid login"

        assert "required" in error.lower() or "username and password do not match" in error.lower(), \
            f"Unexpected error message: {error}"
