"""Seal synchronized original arrow and actor events from one Native tick loop.

The caller supplies a step callback that ticks the world once and reads both
sources after that tick. No aspect or participant state is synthesized here.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from aspect_capture import AspectError, capture as capture_aspects, validate_rows
from saved_aspect import join_event_history


def capture_pair(site, attempt_root, step, *, frames=900, diagnostic=False):
    root = Path(attempt_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    event_path = root / "arrow-events-original.json"
    aspect_path = root / "arrow-aspect-original.json"
    receipt_path = root / "arrow-aspect-receipt.json"
    event_receipt_path = root / "arrow-event-receipt.json"
    if any(p.exists() for p in (event_path, aspect_path, receipt_path,
                                 event_receipt_path)):
        raise AspectError("original arrow source already exists")
    aspects = []
    events = []
    for i in range(frames):
        pair = step(i)
        if not isinstance(pair, tuple) or len(pair) != 2:
            raise AspectError("Native tick must return original aspect and event packets")
        aspect, event = pair
        if not isinstance(aspect, dict) or not isinstance(event, dict):
            raise AspectError("original aspect or event packet missing")
        aspects.append(aspect)
        events.append(event)
    validate_rows(aspects, site, frames=frames)
    for aspect, event in zip(aspects, events):
        if (event.get("frame") != aspect["frame"] or
            str(event.get("official_head_id")) != aspect["head_id"] or
            event.get("facing_approach_id") != aspect["facing_approach_id"] or
            event.get("arrow_movement") != site["arrow_movement"] or
            event.get("concurrent_indications") != aspect["concurrent_indications"]):
            raise AspectError("Native event/aspect identity mismatch")
        lit = event.get("lit_aspects")
        if (not isinstance(lit, list) or
            ("flashing_yellow_turn_arrow" in lit) != aspect["arrow_lit"]):
            raise AspectError("Native event/aspect display mismatch")
        if (not isinstance(event.get("ego_xy"), list) or
            len(event["ego_xy"]) != 2 or
            not isinstance(event.get("other_users"), list)):
            raise AspectError("original actor event source missing")
        if not diagnostic:
            values = [event.get("ego_speed_mps"), event.get("ego_brake"),
                      event.get("ego_heading_deg")]
            if any(type(value) not in (int, float) or not math.isfinite(value)
                   for value in values):
                raise AspectError("original ego kinematic source missing")
            if values[0] < 0 or not 0 <= values[1] <= 1:
                raise AspectError("original ego speed or brake range invalid")
            if (event.get("ego_movement") != site["arrow_movement"] and
                    (not event.get("concurrent_indications") or
                     not event.get("concurrent_permission_source") or
                     event.get("concurrently_permitted_movement") != event.get("ego_movement"))):
                raise AspectError("original concurrent movement permission source missing")
    encoded = (json.dumps(events, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(encoded) > 2 * 1024 * 1024:
        raise AspectError("event source exceeds return file limit")
    capture_aspects(site, root, lambda i: aspects[i], frames=frames,
                    diagnostic=diagnostic)
    event_path.write_bytes(encoded)
    ref = {"path": event_path.name, "sha256": hashlib.sha256(encoded).hexdigest()}
    checked = join_event_history(site, root, ref, delivery=not diagnostic)
    event_receipt_path.write_text(json.dumps({
        "format": "worker-original-arrow-event-v1", "event_ref": ref,
        "aspect_sha256": checked["original_aspect_sha256"],
        "frame_count": checked["frame_count"], "diagnostic": bool(diagnostic),
    }, sort_keys=True) + "\n")
    return {"event_ref": ref, "aspect_sha256": checked["original_aspect_sha256"],
            "frame_count": checked["frame_count"],
            "event_aspect_join": checked["event_aspect_join"],
            "diagnostic": bool(diagnostic), "physical_acceptance": False,
            "legal_verdict": None}
