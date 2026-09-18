"""A small, reusable HTTP client for the API test layer.

Deliberately thin: one `requests.Session` (connection reuse + shared headers),
one place where the base URL and timeout come from configuration, and a
response wrapper that exposes the things tests assert on - status code, JSON
body and round-trip time - without every test re-deriving them.
"""

import logging
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from utils.config import Config

logger = logging.getLogger(__name__)


class APIResponse:
    """Wraps `requests.Response` with the assertions-friendly bits."""

    def __init__(self, response: requests.Response):
        self._response = response

    @property
    def raw(self) -> requests.Response:
        return self._response

    @property
    def status_code(self) -> int:
        return self._response.status_code

    @property
    def ok(self) -> bool:
        return self._response.ok

    @property
    def headers(self):
        return self._response.headers

    @property
    def text(self) -> str:
        return self._response.text

    @property
    def elapsed_ms(self) -> float:
        """Round-trip time in milliseconds, as measured by requests."""
        return self._response.elapsed.total_seconds() * 1000

    def json(self, default: Any = None) -> Any:
        """Parsed JSON body, or `default` when the body is not valid JSON."""
        try:
            return self._response.json()
        except ValueError:
            return default

    def __repr__(self) -> str:
        return (
            f"<APIResponse {self._response.request.method} "
            f"{self._response.url} -> {self.status_code} "
            f"in {self.elapsed_ms:.0f}ms>"
        )


class APIClient:
    """Base-URL aware HTTP client used by the API tests.

    Usage:
        client = APIClient()
        response = client.get("/posts/1")
        assert response.status_code == 200
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        timeout: Optional[int] = None,
        headers: Optional[dict] = None,
        retries: int = 2,
    ):
        self.base_url = (base_url or Config.API_BASE_URL).rstrip("/")
        self.timeout = timeout or Config.API_TIMEOUT
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Accept": "application/json",
                "Content-Type": "application/json; charset=UTF-8",
                "User-Agent": "saucedemo-playwright-framework/api-tests",
            }
        )
        if headers:
            self.session.headers.update(headers)

        # Retry only transport-level and gateway errors, never a real 4xx:
        # a flaky runner should not turn into a red build, but a genuine
        # server-side contract break still fails the test.
        retry = Retry(
            total=retries,
            connect=retries,
            read=retries,
            status=retries,
            backoff_factor=0.5,
            status_forcelist=(429, 502, 503, 504),
            allowed_methods=frozenset(["GET", "HEAD", "OPTIONS", "PUT", "DELETE"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)

    # -- plumbing ----------------------------------------------------------
    def url_for(self, path: str) -> str:
        if path.startswith(("http://", "https://")):
            return path
        return f"{self.base_url}/{path.lstrip('/')}"

    def request(self, method: str, path: str, **kwargs) -> APIResponse:
        url = self.url_for(path)
        kwargs.setdefault("timeout", self.timeout)
        response = self.session.request(method.upper(), url, **kwargs)
        logger.info(
            "%s %s -> %s in %.0fms",
            method.upper(),
            url,
            response.status_code,
            response.elapsed.total_seconds() * 1000,
        )
        return APIResponse(response)

    # -- verbs -------------------------------------------------------------
    def get(self, path: str, **kwargs) -> APIResponse:
        return self.request("GET", path, **kwargs)

    def post(self, path: str, **kwargs) -> APIResponse:
        return self.request("POST", path, **kwargs)

    def put(self, path: str, **kwargs) -> APIResponse:
        return self.request("PUT", path, **kwargs)

    def patch(self, path: str, **kwargs) -> APIResponse:
        return self.request("PATCH", path, **kwargs)

    def delete(self, path: str, **kwargs) -> APIResponse:
        return self.request("DELETE", path, **kwargs)

    def close(self) -> None:
        self.session.close()

    def __enter__(self) -> "APIClient":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()
