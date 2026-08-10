"""Helpers to convert raw MongoDB documents into API-safe dicts.

We never expose Mongo's `_id` directly - the business identifiers
(riskId, accountId, eventId) are the public-facing keys.
"""
from typing import Any


def strip_mongo_id(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    if doc is None:
        return None
    clean = dict(doc)
    clean.pop("_id", None)
    return clean


def strip_mongo_id_list(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [strip_mongo_id(doc) for doc in docs]
