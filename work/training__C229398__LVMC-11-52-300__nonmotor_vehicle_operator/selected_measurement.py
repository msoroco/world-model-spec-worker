"""Recompute the observed nighttime parking episode from joined source frames.

Only a source-reviewed device, activity and street can qualify; the engineering
velocity tolerance measures rest and never defines the legal act of parking.
"""

import argparse
import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from duration_policy import TOTAL_FRAMES, TARGETS
from source_gate import audit as audit_source


def in_night_window(local):
    """Use the source's civil day: 01:00 is included, 06:00 is excluded."""
    return 1 <= local.hour < 6


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure(attempt, *, require_original=False):
    attempt = Path(attempt).resolve()
    config_path = attempt / "config.json"
    actor_path = attempt / "native-actor-frames.jsonl"
    mapping_path = attempt / "video_frames.jsonl"
    context_path = attempt / "review-source.json"
    street_path = attempt / "street-geometry.json"
    for path in (config_path, actor_path, mapping_path, context_path, street_path):
        if not path.is_file():
            raise ValueError("Missing required source: " + path.name)
    cfg = json.loads(config_path.read_text())
    if cfg.get("case_id", "").rsplit("__", 1)[-1] not in TARGETS or cfg.get(
            "capture_frames") != TOTAL_FRAMES or cfg.get("rate_hz") != 20:
        raise ValueError("Exact selected capture contract differs")
    context = audit_source(context_path, require_original=require_original)
    if context["case_id"] != cfg["case_id"]:
        raise ValueError("Source review belongs to another case")
    street = json.loads(street_path.read_text())
    bounds = street.get("street_bounds_xy_m")
    if not isinstance(bounds, list) or len(bounds) != 4 or not all(
            isinstance(value, (int, float)) and math.isfinite(value) for value in bounds):
        raise ValueError("Original street bounds missing")
    if require_original and street.get("source_kind") != "original_native":
        raise ValueError("Original street geometry required")
    findings = json.loads(context_path.read_text())["findings"]
    zone = ZoneInfo(findings["civil_clock"]["iana_timezone"])
    utc_start = findings["civil_clock"]["utc_start_ms"]
    count = 0
    onset = None
    longest_ms = 0
    first_ms = last_ms = None
    first_recording_s = None
    with actor_path.open() as actors, mapping_path.open() as mappings:
        for actor_line, map_line in zip(actors, mappings):
            actor = json.loads(actor_line)
            mapping = json.loads(map_line)
            if actor.get("frame") != count or mapping.get("video_frame") != count or not isinstance(
                    mapping.get("native_frame"), int) or actor.get("native_frame") != mapping[
                    "native_frame"]:
                raise ValueError("Original actor/video frame join differs")
            recording_s = mapping.get("time_s")
            if not isinstance(recording_s, (int, float)) or not math.isfinite(recording_s):
                raise ValueError("Original frame timestamp missing")
            if first_recording_s is None:
                first_recording_s = recording_s
            if abs(recording_s - first_recording_s - count / 20) > 1e-5:
                raise ValueError("Original frame timestamp differs")
            center = actor.get("center_xyz_m")
            velocity = actor.get("velocity_xyz_mps")
            if not isinstance(center, list) or len(center) < 2 or not isinstance(
                    velocity, list) or len(velocity) < 2 or any(not isinstance(v, (int, float))
                    or not math.isfinite(v) for v in (*center[:2], *velocity[:2])):
                raise ValueError("Original actor position or velocity missing")
            ms = utc_start + count * 50
            local = datetime.fromtimestamp(ms / 1000, timezone.utc).astimezone(zone)
            in_window = in_night_window(local)
            on_street = bounds[0] <= center[0] <= bounds[1] and bounds[2] <= center[1] <= bounds[3]
            at_rest = math.hypot(*velocity[:2]) <= .05
            qualifying = (context["qualifying_context_supported"] and in_window
                          and on_street and at_rest)
            if qualifying:
                if onset is None:
                    onset = ms
                longest_ms = max(longest_ms, ms - onset)
            else:
                onset = None
            if first_ms is None:
                first_ms = ms
            last_ms = ms
            count += 1
        if actors.readline() or mappings.readline():
            raise ValueError("Actor/video frame counts differ")
    diagnostic_excerpt = context["source_kind"] == "synthetic_cpu" and 2 <= count <= 2000
    if count != TOTAL_FRAMES and not diagnostic_excerpt:
        raise ValueError("Incomplete thirty-minute source episode")
    return {"format": "c229398-measured-parking-episode-v1",
            "case_id": cfg["case_id"], "source_kind": context["source_kind"],
            "frame_count": count, "first_utc_epoch_ms": first_ms,
            "last_utc_epoch_ms": last_ms,
            "diagnostic_excerpt": diagnostic_excerpt,
            "longest_continuous_qualifying_ms": longest_ms,
            "observed_over_thirty_minutes": longest_ms > 1800000,
            "review_supported": context["qualifying_context_supported"],
            "sources": {path.name: digest(path) for path in
                        (config_path, actor_path, mapping_path, context_path, street_path)},
            "physical_or_legal_acceptance": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--require-original", action="store_true")
    arguments = parser.parse_args()
    print(json.dumps(measure(arguments.attempt, require_original=arguments.require_original)))


if __name__ == "__main__":
    main()
