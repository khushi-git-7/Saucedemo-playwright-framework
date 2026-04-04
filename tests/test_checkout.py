from pages.login_page import LoginPage
from pages.cart_page import CartPage
from pages.checkout_page import CheckoutPage


def test_complete_checkout(browser_page):

    page = browser_page

    login = LoginPage(page)
    login.login("standard_user", "secret_sauce")

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
    
def test_checkout_missing_details(browser_page):

    page = browser_page

    login = LoginPage(page)
    login.login("standard_user", "secret_sauce")

    cart = CartPage(page)
    cart.add_first_product()
    cart.open_cart()

    checkout = CheckoutPage(page)
    checkout.start_checkout()

    checkout.fill_details("", "Test", "625001")

    checkout.click_continue()

    error = checkout.get_error()

    assert error is not None, "Error message not displayed when required checkout details are missing"
    
def test_order_confirmation_text(browser_page):

    page = browser_page

    login = LoginPage(page)
    login.login("standard_user", "secret_sauce")

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
         
    
