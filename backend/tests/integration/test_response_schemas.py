"""
Response-schema contract tests.

For each critical endpoint we assert:
  1. The handler returns the *expected top-level shape* (object vs array).
  2. The *required keys* the frontend relies on are present.

This is the second line of defence (after routing + smoke) against silent
response-shape regressions — e.g. a refactor that drops a field the UI needs,
or starts returning a list where a dict is expected.

The DB is stubbed (conftest.fake_db) so we validate SHAPE, not live data.
"""
import json
from pathlib import Path

import pytest

SCHEMA_PATH = Path(__file__).parent / "api_schemas.json"


def _load_spec():
    with open(SCHEMA_PATH) as f:
        return json.load(f)


SPEC = _load_spec()


@pytest.mark.parametrize("path,spec", list(SPEC.items()))
def test_response_schema(path, spec, client, auth_headers):
    headers = auth_headers if spec.get("auth", False) else {}
    params = spec.get("params")

    resp = client.request(spec["method"], path, headers=headers, params=params)
    # Allow 200 (success) or 422 (validation) but never 500/404/405.
    assert resp.status_code in (200, 422), (
        f"{path} returned unexpected status {resp.status_code}: {resp.text[:300]}"
    )

    if resp.status_code != 200:
        return  # validation error path — shape check not applicable

    body = resp.json()

    expected_type = spec.get("type", "object")
    if expected_type == "array":
        assert isinstance(body, list), f"{path} expected an array, got {type(body)}"
    else:
        assert isinstance(body, dict), f"{path} expected an object, got {type(body)}"

    for key in spec.get("required_keys", []):
        assert key in body, f"{path} missing required key '{key}' in response: {list(body.keys())[:20]}"
