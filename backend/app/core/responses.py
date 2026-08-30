"""Shared Pydantic response models.

We intentionally use ``extra="allow"`` so existing responses (which often carry
many fields the frontend relies on) pass through unchanged. Adding a
``response_model`` here still gives us:
  * OpenAPI documentation of the endpoint's contract
  * a guard that the handler returns the *expected top-level shape*
    (a JSON object for object endpoints, not a bare list/None/string)
"""
from pydantic import BaseModel, ConfigDict


class JsonObject(BaseModel):
    """Permissive JSON object: keeps all extra fields, validates it is a dict."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)
