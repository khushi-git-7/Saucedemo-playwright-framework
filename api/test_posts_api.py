"""Contract tests for the /posts resource.

Covers the four things an API suite is expected to prove:
status code, response schema, response time, and behaviour on a bad request.
"""

import pytest

from api.schemas import CREATED_POST_SCHEMA, POST_LIST_SCHEMA, POST_SCHEMA, validate_schema

pytestmark = pytest.mark.api


@pytest.mark.smoke
@pytest.mark.regression
def test_get_post_returns_200(api_client):

    response = api_client.get("/posts/1")

    assert response.status_code == 200, \
        f"Expected 200 for GET /posts/1, got {response.status_code}"

    assert "application/json" in response.headers.get("Content-Type", ""), \
        f"Expected a JSON content type, got {response.headers.get('Content-Type')!r}"


@pytest.mark.smoke
@pytest.mark.regression
def test_get_post_matches_schema(api_client):

    response = api_client.get("/posts/1")

    body = response.json()

    assert response.status_code == 200

    validate_schema(body, POST_SCHEMA, context="GET /posts/1")

    assert body["id"] == 1, f"Requested post 1 but the payload reports id={body['id']}"


@pytest.mark.regression
def test_list_posts_matches_collection_schema(api_client):

    response = api_client.get("/posts")

    assert response.status_code == 200

    body = response.json()

    validate_schema(body, POST_LIST_SCHEMA, context="GET /posts")

    ids = [item["id"] for item in body]

    assert len(ids) == len(set(ids)), "GET /posts returned duplicate post ids"


@pytest.mark.regression
def test_get_post_responds_within_sla(api_client, max_response_ms):

    response = api_client.get("/posts/1")

    assert response.status_code == 200

    assert response.elapsed_ms < max_response_ms, \
        f"GET /posts/1 took {response.elapsed_ms:.0f}ms, SLA is {max_response_ms}ms"


@pytest.mark.regression
def test_create_post_returns_201(api_client):

    payload = {
        "title": "playwright framework smoke",
        "body": "created by the api test layer",
        "userId": 1,
    }

    response = api_client.post("/posts", json=payload)

    assert response.status_code == 201, \
        f"Expected 201 for POST /posts, got {response.status_code}"

    body = response.json()

    validate_schema(body, CREATED_POST_SCHEMA, context="POST /posts")

    assert body["title"] == payload["title"], \
        "The created resource did not echo back the title that was sent"


# --- negative cases -------------------------------------------------------
@pytest.mark.regression
def test_get_unknown_post_returns_404(api_client):
    """A resource that does not exist must be a 404, not an empty 200."""

    response = api_client.get("/posts/999999")

    assert response.status_code == 404, \
        f"Expected 404 for an unknown post, got {response.status_code}"

    assert not response.json(default={}), \
        "Expected an empty body for an unknown post"


@pytest.mark.regression
def test_unknown_endpoint_returns_404(api_client):

    response = api_client.get("/this-endpoint-does-not-exist")

    assert response.status_code == 404, \
        f"Expected 404 for an unknown endpoint, got {response.status_code}"
