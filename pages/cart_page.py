from playwright.sync_api import Page

class CartPage:

    def __init__(self, page: Page):

        self.page = page

        self.add_to_cart_button = "button[data-test^='add-to-cart']"
        self.remove_button = "button[data-test^='remove']"
        self.cart_badge = ".shopping_cart_badge"
        self.cart_icon = ".shopping_cart_link"
        self.cart_items = ".cart_item"
        self.cart_list = ".cart_list"

    def add_first_product(self):

        self.page.locator(self.add_to_cart_button).first.click()

    def remove_first_product(self):

        self.page.locator(self.remove_button).first.click()

    def get_cart_count(self):

        badge = self.page.locator(self.cart_badge)

        if badge.count() == 0:
            return 0

        return int(badge.inner_text())

    def open_cart(self):

        self.page.click(self.cart_icon)

    def get_cart_items(self):

        # The cart page must have rendered before its rows are counted;
        # waiting on the list container (not a row) keeps an empty cart valid.
        self.page.locator(self.cart_list).wait_for(state="visible")

        return self.page.locator(self.cart_items).count()