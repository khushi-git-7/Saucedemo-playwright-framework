import pytest

from pages.login_page import LoginPage
from pages.cart_page import CartPage
from pages.checkout_page import CheckoutPage
from utils.config import Config

pytestmark = pytest.mark.ui


@pytest.mark.e2e
@pytest.mark.smoke
@pytest.mark.regression
def test_complete_checkout(browser_page):

    page = browser_page

    login = LoginPage(page)
    login.login(Config.STANDARD_USER, Config.PASSWORD)

    cart = CartPage(page)
    cart.add_first_product()
    cart.open_cart()

    checkout = CheckoutPage(page)
    checkout.start_checkout()

    checkout.fill_details("Khushi", "Test", "625001")

    checkout.click_continue()
    checkout.click_finish()

    confirmation = checkout.get_confirmation()

    assert "thank you" in confirmation.lower(), "Order confirmation message does not contain 'Thank you' or is not displayed"


@pytest.mark.regression
def test_checkout_missing_details(browser_page):

    page = browser_page

    login = LoginPage(page)
    login.login(Config.STANDARD_USER, Config.PASSWORD)

    cart = CartPage(page)
    cart.add_first_product()
    cart.open_cart()

    checkout = CheckoutPage(page)
    checkout.start_checkout()

    checkout.fill_details("", "Test", "625001")

    checkout.click_continue()

    error = checkout.get_error()

    assert error is not None, "Error message not displayed when required checkout details are missing"


@pytest.mark.e2e
@pytest.mark.regression
def test_order_confirmation_text(browser_page):

    page = browser_page

    login = LoginPage(page)
    login.login(Config.STANDARD_USER, Config.PASSWORD)

    cart = CartPage(page)
    cart.add_first_product()
    cart.open_cart()

    checkout = CheckoutPage(page)
    checkout.start_checkout()

    checkout.fill_details("Khushi", "Test", "625001")

    checkout.click_continue()
    checkout.click_finish()

    confirmation = checkout.get_confirmation()

    assert confirmation == "Thank you for your order!", \
        f"unexpected order confirmation text: '{confirmation}'"
