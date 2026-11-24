"""Independent source-bound comparison for the two door-duration probes.

This compares original Native trace envelopes; it does not decide whether an
observed interval was necessary for immediate loading or unloading.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from measure_door import FRAME_COUNT, FPS, VIEWS, measure

FIXED = (
    "map_source_sha256", "road_id", "ego_blueprint", "passing_blueprint",
    "traffic_lane_id", "ego_spawn", "passing_spawn", "transfer_kind",
    "transfer_frame", "camera_plan_sha256", "controller_policy_sha256",
)


def _context(packet: dict) -> dict:
    context = packet.get("construction_context")
    if not isinstance(context, dict) or any(not context.get(key) for key in FIXED):
        raise ValueError("complete source-bound construction context required")
    if context.get("fps") != FPS or context.get("frame_count") != FRAME_COUNT:
        raise ValueError("common 20 Hz, 600-frame capture contract required")
    if context.get("camera_names") != list(VIEWS):
        raise ValueError("common four-camera plan required")
    event = packet.get("transfer_events", [])
    if len(event) != 1 or event[0].get("kind") != context["transfer_kind"] or event[0].get("native_frame") != context["transfer_frame"]:
        raise ValueError("transfer event differs from construction context")
    return context


def compare(reference: dict, contrast: dict) -> dict:
    if reference.get("case_id", "").split("__")[-1] != "probe_1" or contrast.get("case_id", "").split("__")[-1] != "probe_2":
        raise ValueError("exact probe order required")
    if reference.get("case_id", "").removesuffix("probe_1") != contrast.get("case_id", "").removesuffix("probe_2"):
        raise ValueError("comparison cases must share assignment")
    left = _context(reference)
    right = _context(contrast)
    changed = [key for key in FIXED if left[key] != right[key]]
    if changed:
        raise ValueError("fixed construction changed: " + ", ".join(changed))
    if reference.get("source_sha256") == contrast.get("source_sha256"):
        raise ValueError("distinct original Native trace sources required")
    if reference.get("driver_actor_id") == reference.get("passing_vehicle", {}).get("actor_id") or contrast.get("driver_actor_id") == contrast.get("passing_vehicle", {}).get("actor_id"):
        raise ValueError("passing vehicle and door operator must differ")
    for name in VIEWS:
        if reference["cameras"][name]["sha256"] == contrast["cameras"][name]["sha256"]:
            raise ValueError("distinct source-camera video required: " + name)
    a, b = measure(reference), measure(contrast)
    if a["door_side"] != b["door_side"] or a["passing_side"] != b["passing_side"]:
        raise ValueError("traffic-side geometry changed")
    if a["open_frame"] != b["open_frame"] or a["last_transfer_frame"] != b["last_transfer_frame"] or a["transfer_kinds"] != b["transfer_kinds"]:
        raise ValueError("opening or transfer event changed")
    if a["close_frame"] == b["close_frame"]:
        raise ValueError("door closing comparison has no measured difference")
    return {
        "format": "worker-independent-door-comparison", "passed": True,
        "case_ids": [reference["case_id"], contrast["case_id"]],
        "source_sha256": [a["source_sha256"], b["source_sha256"]],
        "fixed_context": {key: left[key] for key in FIXED},
        "open_frame": a["open_frame"],
        "transfer_frame": a["last_transfer_frame"],
        "close_frames": [a["close_frame"], b["close_frame"]],
        "post_transfer_open_s": [a["post_transfer_open_s"], b["post_transfer_open_s"]],
        "measured_close_difference_s": (b["close_frame"] - a["close_frame"]) / FPS,
        "legal_necessity": "unresolved_requires_contextual_review",
        "physical_acceptance": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("reference", type=Path)
    parser.add_argument("contrast", type=Path)
    parser.add_argument("--reference-sha256", required=True)
    parser.add_argument("--contrast-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("comparison output must be new")
    sources = [args.reference, args.contrast]
    packets = [json.loads(path.read_text()) for path in sources]
    for path, expected in zip(sources, (args.reference_sha256, args.contrast_sha256)):
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("source packet hash mismatch: " + str(path))
    result = compare(*packets)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"passed": True, "measured_close_difference_s": result["measured_close_difference_s"]}))


if __name__ == "__main__":
    main()
