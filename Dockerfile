# Official Playwright image: Python + the browsers + every system library they
# need, already installed under /ms-playwright. The tag must stay in sync with
# the playwright version pinned in requirements.txt.
FROM mcr.microsoft.com/playwright/python:v1.58.0-noble

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    HEADED=0

WORKDIR /app

# A virtualenv keeps pip away from the Debian/Ubuntu managed system Python
# (PEP 668) while still resolving browsers from PLAYWRIGHT_BROWSERS_PATH,
# which the base image already points at /ms-playwright.
ENV VIRTUAL_ENV=/opt/venv
RUN python3 -m venv "$VIRTUAL_ENV"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# Dependencies first so that code changes do not invalidate the pip layer.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Default run: the whole suite, headless, one process per available CPU.
# Override at run time, e.g.  docker run --rm <image> -m smoke
ENTRYPOINT ["python", "-m", "pytest"]
CMD ["-n", "auto"]
