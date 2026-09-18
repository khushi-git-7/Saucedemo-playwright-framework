import pytest

from pages.login_page import LoginPage
from pages.cart_page import CartPage
from utils.config import Config

pytestmark = pytest.mark.ui


@pytest.mark.smoke
@pytest.mark.regression
def test_add_product_to_cart(browser_page):

    page = browser_page

    login = LoginPage(page)

    login.login(Config.STANDARD_USER, Config.PASSWORD)

    cart = CartPage(page)

    cart.add_first_product()

    count = cart.get_cart_count()

    assert count == 1, f"Expected cart count to be 1 after adding product, but got {count}"


@pytest.mark.regression
def test_remove_product_from_cart(browser_page):

    page = browser_page

    login = LoginPage(page)

    login.login(Config.STANDARD_USER, Config.PASSWORD)

    cart = CartPage(page)

    cart.add_first_product()

    cart.remove_first_product()

    count = cart.get_cart_count()

    assert count == 0, f"Expected cart count to be 0 after removing product, but got {count}"


@pytest.mark.regression
def test_cart_item_visible(browser_page):

    page = browser_page

    login = LoginPage(page)

    login.login(Config.STANDARD_USER, Config.PASSWORD)

    cart = CartPage(page)

    cart.add_first_product()

    cart.open_cart()

    items = cart.get_cart_items()

    assert items == 1, f"Expected 1 item in cart, but found {items}"
