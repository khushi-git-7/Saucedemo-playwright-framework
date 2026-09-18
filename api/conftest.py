"""Fixtures for the API layer.

The client is session scoped so that one `requests.Session` (and therefore one
pooled TCP/TLS connection) is reused across the API tests in a worker. The API
tests are stateless reads plus one create, so sharing the session is safe -
including under `pytest -n auto`, where each worker builds its own client.
"""

import pytest

from api.client import APIClient
from utils.config import Config


@pytest.fixture(scope="session")
def api_client():
    client = APIClient(base_url=Config.API_BASE_URL, timeout=Config.API_TIMEOUT)
    yield client
    client.close()


@pytest.fixture(scope="session")
def max_response_ms() -> int:
    """SLA used by the response-time assertions (API_MAX_RESPONSE_MS)."""
    return Config.API_MAX_RESPONSE_MS
