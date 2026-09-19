"""Repository-level pytest configuration.

Registers the results recorder (utils/results_plugin.py) for every layer, so a
UI run, an API run and a full run all leave a JSON record under
reports/history/ for the dashboard. Layer-specific fixtures live in
tests/conftest.py and api/conftest.py.
"""

pytest_plugins = ["utils.results_plugin"]
