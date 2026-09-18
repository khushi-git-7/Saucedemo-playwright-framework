"""Central configuration for the framework.

Every value is read from an environment variable with a sane default, so the
same test code runs locally, in Docker and in CI without edits. A local `.env`
file (see `.env.example`) is loaded automatically when `python-dotenv` is
installed - it is never committed.

Nothing here is a secret: SauceDemo is a public demo application. The point of
routing credentials through the environment is that the *pattern* is correct -
no credential literal ever lands in a test file.
"""

import os
from pathlib import Path

try:  # python-dotenv is optional - the framework works without it
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - only hit when dotenv is absent
    load_dotenv = None

# Repository root: <root>/utils/config.py -> <root>
ROOT_DIR = Path(__file__).resolve().parent.parent

if load_dotenv is not None:
    load_dotenv(ROOT_DIR / ".env", override=False)

_TRUTHY = {"1", "true", "yes", "on", "y"}
_ARTIFACT_MODES = {"on", "off", "retain-on-failure"}


def _env_str(name: str, default: str) -> str:
    value = os.getenv(name)
    return default if value is None or value.strip() == "" else value.strip()


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in _TRUTHY


def _env_int(name: str, default: int) -> int:
    try:
        return int(_env_str(name, str(default)))
    except ValueError:
        return default


def _env_mode(name: str, default: str) -> str:
    """Playwright-style artifact mode: on | off | retain-on-failure."""
    value = _env_str(name, default).lower()
    return value if value in _ARTIFACT_MODES else default


class Config:
    """Immutable-by-convention settings object shared by UI and API tests."""

    # --- Application under test -------------------------------------------
    BASE_URL = _env_str("BASE_URL", "https://www.saucedemo.com/")

    # --- Credentials (env driven, never hardcoded in a test) ---------------
    STANDARD_USER = _env_str("SAUCE_USERNAME", "standard_user")
    PASSWORD = _env_str("SAUCE_PASSWORD", "secret_sauce")
    LOCKED_OUT_USER = _env_str("SAUCE_LOCKED_USER", "locked_out_user")
    PROBLEM_USER = _env_str("SAUCE_PROBLEM_USER", "problem_user")

    # --- Browser ----------------------------------------------------------
    # chromium | firefox | webkit
    BROWSER = _env_str("BROWSER", "chromium").lower()
    # Headless by default; HEADED=1 flips it (CI stays headless, always).
    HEADLESS = not _env_bool("HEADED", False)
    SLOW_MO = _env_int("SLOW_MO", 0)  # milliseconds, 0 = full speed
    VIEWPORT_WIDTH = _env_int("VIEWPORT_WIDTH", 1440)
    VIEWPORT_HEIGHT = _env_int("VIEWPORT_HEIGHT", 900)

    # --- Timeouts (milliseconds) ------------------------------------------
    TIMEOUT = _env_int("TIMEOUT", 15_000)
    NAVIGATION_TIMEOUT = _env_int("NAVIGATION_TIMEOUT", 30_000)

    # --- Failure artifacts -------------------------------------------------
    SCREENSHOT = _env_mode("SCREENSHOT", "retain-on-failure")
    TRACE = _env_mode("TRACE", "retain-on-failure")
    VIDEO = _env_mode("VIDEO", "retain-on-failure")

    # --- API layer ---------------------------------------------------------
    API_BASE_URL = _env_str("API_BASE_URL", "https://jsonplaceholder.typicode.com")
    API_TIMEOUT = _env_int("API_TIMEOUT", 15)  # seconds, passed to requests
    API_MAX_RESPONSE_MS = _env_int("API_MAX_RESPONSE_MS", 3_000)

    # --- Paths -------------------------------------------------------------
    ROOT_DIR = ROOT_DIR
    TEST_DATA_DIR = ROOT_DIR / "test_data"
    REPORTS_DIR = ROOT_DIR / "reports"
    SCREENSHOTS_DIR = ROOT_DIR / "screenshots"
    TRACES_DIR = ROOT_DIR / "traces"
    VIDEOS_DIR = ROOT_DIR / "videos"

    SUPPORTED_BROWSERS = ("chromium", "firefox", "webkit")

    @classmethod
    def validate(cls) -> None:
        """Fail fast on a bad environment instead of deep inside a fixture."""
        if cls.BROWSER not in cls.SUPPORTED_BROWSERS:
            raise ValueError(
                f"Unsupported BROWSER={cls.BROWSER!r}. "
                f"Expected one of {', '.join(cls.SUPPORTED_BROWSERS)}."
            )
        if not cls.BASE_URL.startswith(("http://", "https://")):
            raise ValueError(f"BASE_URL must be an absolute URL, got {cls.BASE_URL!r}")

    @classmethod
    def as_dict(cls) -> dict:
        """Non-secret view of the config, used for report metadata."""
        return {
            "base_url": cls.BASE_URL,
            "api_base_url": cls.API_BASE_URL,
            "browser": cls.BROWSER,
            "headless": cls.HEADLESS,
            "slow_mo_ms": cls.SLOW_MO,
            "timeout_ms": cls.TIMEOUT,
            "trace": cls.TRACE,
            "video": cls.VIDEO,
            "screenshot": cls.SCREENSHOT,
        }


config = Config

# Backwards compatible module-level constant (the original framework imported
# `from utils.config import BASE_URL`).
BASE_URL = Config.BASE_URL
