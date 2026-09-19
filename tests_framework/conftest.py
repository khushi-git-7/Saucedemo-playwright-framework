"""Configuration for the framework's own unit tests.

These tests exercise the dashboard generator and the results recorder with
synthetic data. They are not application results, so the recorder is switched
off for this session and nothing lands in reports/history/.

``pytester`` runs small throwaway pytest sessions in-process, which is how the
recorder's hook behaviour is tested end to end (see test_results_plugin.py).
"""

from utils import results_plugin

pytest_plugins = ["pytester"]


def pytest_configure(config):
    config.stash[results_plugin.DISABLED_KEY] = True
