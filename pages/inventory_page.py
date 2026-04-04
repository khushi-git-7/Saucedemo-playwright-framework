from playwright.sync_api import Page


class InventoryPage:

    def __init__(self, page: Page):

        self.page = page

        self.product_names = ".inventory_item_name"
        self.product_prices = ".inventory_item_price"
        self.sort_dropdown = ".product_sort_container"

    def get_product_names(self):

        elements = self.page.locator(self.product_names).all()

        names = []

        for element in elements:
            names.append(element.inner_text())

        return names

    def get_product_prices(self):

        elements = self.page.locator(self.product_prices).all()

        prices = []

        for element in elements:

            price_text = element.inner_text()

            price = float(price_text.replace("$", ""))

            prices.append(price)

        return prices

    def sort_by(self, option):

        self.page.select_option(self.sort_dropdown, option)