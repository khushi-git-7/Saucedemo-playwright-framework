"""Configuration for the framework's own unit tests.

These tests exercise the dashboard generator and the results recorder with
synthetic data. They are not application results, so the recorder is switched
off for this session and nothing lands in reports/history/.
"""

from utils import results_plugin


def pytest_configure(config):
    config.stash[results_plugin.DISABLED_KEY] = True
