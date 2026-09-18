"""JSON Schemas (draft 2020-12) for the API under test, plus a helper that
turns a schema violation into a readable pytest failure.

Keeping schemas next to the client - rather than inline in each test - means a
contract change is a one-line diff in one file.
"""

import jsonschema

POST_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["userId", "id", "title", "body"],
    "additionalProperties": False,
    "properties": {
        "userId": {"type": "integer", "minimum": 1},
        "id": {"type": "integer", "minimum": 1},
        "title": {"type": "string", "minLength": 1},
        "body": {"type": "string"},
    },
}

POST_LIST_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "array",
    "minItems": 1,
    "items": POST_SCHEMA,
}

CREATED_POST_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["id"],
    "properties": {
        "id": {"type": "integer"},
        "title": {"type": "string"},
        "body": {"type": "string"},
        "userId": {"type": ["integer", "string"]},
    },
}

USER_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "type": "object",
    "required": ["id", "name", "username", "email", "address"],
    "properties": {
        "id": {"type": "integer", "minimum": 1},
        "name": {"type": "string", "minLength": 1},
        "username": {"type": "string", "minLength": 1},
        # Format checking is off by default in jsonschema, so the pattern does
        # the actual work here.
        "email": {"type": "string", "pattern": r"^[^@\s]+@[^@\s]+\.[^@\s]+$"},
        "address": {
            "type": "object",
            "required": ["street", "city", "zipcode"],
            "properties": {
                "street": {"type": "string"},
                "city": {"type": "string"},
                "zipcode": {"type": "string"},
            },
        },
    },
}


def validate_schema(instance, schema, context: str = "response body") -> None:
    """Validates `instance` against `schema`, failing with a readable message."""
    try:
        jsonschema.validate(instance=instance, schema=schema)
    except jsonschema.ValidationError as error:
        location = "/".join(str(part) for part in error.absolute_path) or "<root>"
        raise AssertionError(
            f"JSON schema validation failed for {context}\n"
            f"  at: {location}\n"
            f"  problem: {error.message}"
        ) from error
