"""Independent saved-only check of sealed original arrow display history."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from aspect_capture import AspectError, validate_rows


def audit(site, attempt_root, *, delivery=True):
    root = Path(attempt_root).resolve()
    receipt_path = root / "arrow-aspect-receipt.json"
    if not receipt_path.is_file():
        raise AspectError("aspect receipt missing")
    receipt = json.loads(receipt_path.read_text())
    if receipt.get("format") != "worker-original-arrow-aspect-v1":
        raise AspectError("aspect receipt format mismatch")
    if delivery and receipt.get("diagnostic") is not False:
        raise AspectError("diagnostic aspect source cannot prove delivery")
    source = (root / str(receipt.get("source_path", ""))).resolve()
    if not source.is_relative_to(root) or not source.is_file():
        raise AspectError("aspect original source missing or escapes attempt")
    raw = source.read_bytes()
    if hashlib.sha256(raw).hexdigest() != receipt.get("source_sha256"):
        raise AspectError("aspect original source hash mismatch")
    rows = json.loads(raw)
    if not isinstance(rows, list):
        raise AspectError("aspect original frame history missing")
    transitions = validate_rows(rows, site, frames=receipt.get("frame_count"))
    if (receipt.get("frequency_hz") != 20 or
        receipt.get("first_frame") != rows[0]["frame"] or
        str(receipt.get("head_id")) != str(site["official_head_id"]) or
        receipt.get("facing_approach_id") != site["ego_approach_id"] or
        receipt.get("arrow_direction") != site["arrow_movement"] or
        receipt.get("observed_transitions") != transitions):
        raise AspectError("aspect receipt does not bind original observations")
    return {
        "original_aspect_sha256": receipt["source_sha256"],
        "frame_count": len(rows),
        "observed_transitions": transitions,
        "physical_acceptance": False,
        "legal_verdict": None,
    }


def join_event_history(site, attempt_root, event_ref, *, delivery=True):
    """Reject a trajectory/event history that invents or drops an arrow state."""
    checked = audit(site, attempt_root, delivery=delivery)
    root = Path(attempt_root).resolve()
    event_path = (root / str(event_ref.get("path", ""))).resolve()
    if not event_path.is_relative_to(root) or not event_path.is_file():
        raise AspectError("original event source missing or escapes attempt")
    raw = event_path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != event_ref.get("sha256"):
        raise AspectError("original event source hash mismatch")
    events = json.loads(raw)
    aspects = json.loads((root / "arrow-aspect-original.json").read_text())
    if not isinstance(events, list) or len(events) != len(aspects):
        raise AspectError("event/aspect frame histories do not join")
    for event, aspect in zip(events, aspects):
        if (event.get("frame") != aspect["frame"] or
            str(event.get("official_head_id")) != aspect["head_id"] or
            event.get("facing_approach_id") != aspect["facing_approach_id"]):
            raise AspectError("event/aspect frame identity mismatch")
        lit = event.get("lit_aspects")
        if (not isinstance(lit, list) or
            ("flashing_yellow_turn_arrow" in lit) != aspect["arrow_lit"] or
            event.get("concurrent_indications") != aspect["concurrent_indications"]):
            raise AspectError("event/aspect display mismatch")
    return {
        **checked,
        "original_event_sha256": event_ref["sha256"],
        "event_aspect_join": True,
    }
