"""Contract tests for the /users resource."""

import pytest

from api.schemas import USER_SCHEMA, validate_schema

pytestmark = pytest.mark.api


@pytest.mark.smoke
@pytest.mark.regression
def test_get_user_returns_200_and_matches_schema(api_client):

    response = api_client.get("/users/1")

    assert response.status_code == 200, \
        f"Expected 200 for GET /users/1, got {response.status_code}"

    validate_schema(response.json(), USER_SCHEMA, context="GET /users/1")


@pytest.mark.regression
@pytest.mark.parametrize("user_id", [1, 2, 3])
def test_every_user_has_a_valid_email(api_client, user_id):
    """The email pattern lives in the schema, so this is a real contract check."""

    response = api_client.get(f"/users/{user_id}")

    assert response.status_code == 200

    body = response.json()

    validate_schema(body, USER_SCHEMA, context=f"GET /users/{user_id}")

    assert body["id"] == user_id


@pytest.mark.regression
def test_filter_posts_by_user_returns_only_that_user(api_client):

    response = api_client.get("/posts", params={"userId": 1})

    assert response.status_code == 200

    body = response.json()

    assert body, "Expected at least one post for userId=1"

    assert all(item["userId"] == 1 for item in body), \
        "GET /posts?userId=1 returned posts belonging to another user"
