from playwright.sync_api import Page


class InventoryPage:

    def __init__(self, page: Page):

        self.page = page

        self.product_names = ".inventory_item_name"
        self.product_prices = ".inventory_item_price"
        self.sort_dropdown = ".product_sort_container"

    def _wait_for_products(self, selector):
        """Wait until the product list has rendered before reading it.

        `Locator.all()` deliberately does not auto-wait: it snapshots whatever
        is in the DOM at that instant, which right after login can be nothing.
        Waiting for the first item to be visible makes every read below
        deterministic.
        """
        locator = self.page.locator(selector)
        locator.first.wait_for(state="visible")
        return locator

    def get_product_names(self):

        return self._wait_for_products(self.product_names).all_inner_texts()

    def get_product_prices(self):

        prices = []

        for price_text in self._wait_for_products(self.product_prices).all_inner_texts():

            prices.append(float(price_text.replace("$", "")))

        return prices

    def sort_by(self, option):

        self.page.select_option(self.sort_dropdown, option)