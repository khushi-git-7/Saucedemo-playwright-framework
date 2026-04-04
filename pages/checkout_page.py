from playwright.sync_api import Page


class CheckoutPage:

    def __init__(self, page: Page):

        self.page = page

        self.checkout_button = "#checkout"
        self.first_name = "#first-name"
        self.last_name = "#last-name"
        self.postal_code = "#postal-code"
        self.continue_button = "#continue"
        self.finish_button = "#finish"
        self.error_message = "[data-test='error']"
        self.confirmation_text = ".complete-header"

    def start_checkout(self):

        self.page.click(self.checkout_button)

    def fill_details(self, fname, lname, zip_code):

        self.page.fill(self.first_name, fname)
        self.page.fill(self.last_name, lname)
        self.page.fill(self.postal_code, zip_code)

    def click_continue(self):

        self.page.click(self.continue_button)

    def click_finish(self):

        self.page.click(self.finish_button)

    def get_error(self):

        return self.page.text_content(self.error_message)

    def get_confirmation(self):

        return self.page.text_content(self.confirmation_text)