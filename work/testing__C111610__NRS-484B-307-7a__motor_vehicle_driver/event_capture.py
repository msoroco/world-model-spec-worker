"""Seal synchronized original arrow and actor events from one Native tick loop.

The caller supplies a step callback that ticks the world once and reads both
sources after that tick. No aspect or participant state is synthesized here.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from aspect_capture import AspectError, capture as capture_aspects, validate_rows
from saved_aspect import join_event_history


def capture_pair(site, attempt_root, step, *, frames=900, diagnostic=False):
    root = Path(attempt_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    event_path = root / "arrow-events-original.json"
    aspect_path = root / "arrow-aspect-original.json"
    receipt_path = root / "arrow-aspect-receipt.json"
    if any(p.exists() for p in (event_path, aspect_path, receipt_path)):
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
    encoded = (json.dumps(events, sort_keys=True, separators=(",", ":")) + "\n").encode()
    if len(encoded) > 2 * 1024 * 1024:
        raise AspectError("event source exceeds return file limit")
    capture_aspects(site, root, lambda i: aspects[i], frames=frames,
                    diagnostic=diagnostic)
    event_path.write_bytes(encoded)
    ref = {"path": event_path.name, "sha256": hashlib.sha256(encoded).hexdigest()}
    checked = join_event_history(site, root, ref, delivery=not diagnostic)
    return {"event_ref": ref, "aspect_sha256": checked["original_aspect_sha256"],
            "frame_count": checked["frame_count"],
            "event_aspect_join": checked["event_aspect_join"],
            "diagnostic": bool(diagnostic), "physical_acceptance": False,
            "legal_verdict": None}
