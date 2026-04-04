🛒 E-commerce Automation Framework (Playwright + Pytest)

📌 Project Overview

This project is a **UI Test Automation Framework** built using **Playwright (Python) and Pytest**.

It automates core functionalities of an e-commerce web application including:

* Login functionality
* Product inventory validation
* Cart operations
* Checkout process

The framework follows **Page Object Model (POM)** and includes **data-driven testing, reusable fixtures, and failure handling mechanisms**.


🚀 Tech Stack

* Python
* Playwright
* Pytest
* Pytest HTML Reports


📂 Project Structure

```
ecommerce_playwright_framework
│
├── pages
│   ├── login_page.py
│   ├── inventory_page.py
│   ├── cart_page.py
│   └── checkout_page.py
│
├── tests
│   ├── test_login.py
│   ├── test_inventory.py
│   ├── test_cart.py
│   └── test_checkout.py
│
├── test_data
│   └── login_data.json
│
├── utils
│   └── config.py
│
├── screenshots
├── reports
│
├── pytest.ini
├── requirements.txt
└── README.md
```



✅ Features Implemented

🔐 Login Testing

* Valid login
* Invalid credentials
* Locked user validation
* Empty field validation
* Data-driven testing using JSON

🛍️ Inventory Page Testing

* Verify product visibility
* Validate product names and prices
* Sorting validation (Low → High, High → Low)

🛒 Cart Functionality

* Add product to cart
* Remove product from cart
* Validate cart badge count
* Verify items inside cart

💳 Checkout Flow

* Complete end-to-end checkout
* Validate missing user details
* Verify order confirmation message


🧠 Key Concepts Used

* Page Object Model (POM)
* Data-driven testing (Pytest parameterization)
* Fixtures for browser setup
* Assertions for UI validation
* Handling dynamic elements
* End-to-end test automation

📸 Screenshot on Failure

The framework automatically captures screenshots when a test fails.

This helps in:

* Debugging failures
* Understanding UI issues
* Analyzing test results in CI/CD environments

Screenshots are saved in the `screenshots/` folder with timestamp.


📊 Test Execution

Run all tests
pytest

Run specific test file:
pytest tests/test_login.py


📈 HTML Report

After execution, open:

reports/report.html

This shows:

* Test results
* Pass/Fail status
* Execution details

💡 What This Project Demonstrates

* Real-world automation framework design
* Clean code structure
* Scalable test architecture
* Strong understanding of QA concepts
* Practical Playwright + Pytest usage

🔗 Application Under Test

https://www.saucedemo.com/

👩‍💻 Author

Khushi Jain
Aspiring QA Engineer | Playwright | Pytest | Automation Testing
