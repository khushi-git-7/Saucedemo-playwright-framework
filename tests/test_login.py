import json
import pytest
from pages.login_page import LoginPage


def load_test_data():
    with open("test_data/login_data.json") as f:
        return json.load(f)


@pytest.mark.parametrize("data", load_test_data())
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

