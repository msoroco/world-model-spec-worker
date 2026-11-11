"""Validate separately retained premises for the emergency-vehicle exception.

The source records a dispatch assertion for later review. It cannot turn a
vehicle blueprint or warning lamp into proof of legal authorization.
"""

from hashlib import sha256
import json
from pathlib import Path


def read_exception_source(root, context, ego_id):
    """Require an actor-bound original source whenever an exception is asserted."""
    if not (context["subject_authorized_emergency"] or context["subject_official_business"]):
        return None
    path = Path(root) / "subject_exception_source.json"
    if not path.is_file():
        raise ValueError("Missing required source: subject_exception_source.json")
    raw = path.read_bytes()
    try:
        source = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Invalid subject exception source") from error
    if source.get("ego_id") != ego_id:
        raise ValueError("Subject exception source actor identity differs")
    for key, context_key in (("authorized_emergency", "subject_authorized_emergency"),
                             ("official_business", "subject_official_business")):
        item = source.get(key)
        if not isinstance(item, dict) or type(item.get("asserted")) is not bool:
            raise ValueError("Subject exception premise needs an explicit assertion: " + key)
        if item["asserted"] != context[context_key]:
            raise ValueError("Subject exception premise conflicts with capture context: " + key)
        if not isinstance(item.get("source_ref"), str) or not item["source_ref"].strip():
            raise ValueError("Subject exception premise lacks source reference: " + key)
    return {"value": source, "sha256": sha256(raw).hexdigest()}
