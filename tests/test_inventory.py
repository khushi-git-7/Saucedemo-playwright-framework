from pages.login_page import LoginPage
from pages.inventory_page import InventoryPage

#to test if product loads and is visible on the inventory page after login
def test_products_visible(browser_page):

    page = browser_page

    login_page = LoginPage(page)

    login_page.login("standard_user", "secret_sauce")

    inventory_page = InventoryPage(page)

    product_names = inventory_page.get_product_names()

    assert len(product_names) > 0, "Products not visible on inventory page after login"


#to test if product names are not empty on the inventory page after login
def test_product_names_exist(browser_page):

    page = browser_page

    login_page = LoginPage(page)

    login_page.login("standard_user", "secret_sauce")

    inventory_page = InventoryPage(page)

    names = inventory_page.get_product_names()

    for name in names:

        assert len(name.strip()) > 0, "Product name is empty on inventory page"
        
        
#to test if product prices are visible and greater than 0 on the inventory page after login
def test_product_prices_exist(browser_page):

    page = browser_page

    login_page = LoginPage(page)

    login_page.login("standard_user", "secret_sauce")

    inventory_page = InventoryPage(page)

    prices = inventory_page.get_product_prices()

    for price in prices:

        assert price > 0, f"Invalid price found: {price}"
        
#to test if sorting products by price low to high works correctly on the inventory page

def test_sort_price_low_to_high(browser_page):

    page = browser_page

    login_page = LoginPage(page)

    login_page.login("standard_user", "secret_sauce")

    inventory_page = InventoryPage(page)

    inventory_page.sort_by("lohi")

    prices = inventory_page.get_product_prices()

    sorted_prices = sorted(prices)

    assert prices == sorted_prices, "Products are not sorted by price low to high correctly on inventory page"
    
#to test if sorting products by price high to low works correctly on the inventory page

def test_sort_price_high_to_low(browser_page):

    page = browser_page

    login_page = LoginPage(page)

    login_page.login("standard_user", "secret_sauce")

    inventory_page = InventoryPage(page)

    inventory_page.sort_by("hilo")

    prices = inventory_page.get_product_prices()

    sorted_prices = sorted(prices, reverse=True)

    assert prices == sorted_prices, "Products are not sorted by price high to low correctly on inventory page"

