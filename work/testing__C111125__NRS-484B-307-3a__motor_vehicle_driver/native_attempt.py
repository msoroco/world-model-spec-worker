"""Record one 20 Hz Native attempt using original, source-sealed lamp packets.

The caller supplies a surveyed site, spawned actors and a controller. Lamp
packets must come from an independent observation source; CARLA Green alone is
insufficient to establish a simultaneously illuminated turn arrow.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from dual_green import check_site, read_source, require


def _packet(root, ref, frame, site):
    packet = json.loads(read_source(root, ref).read_text(encoding="utf-8"))
    require(packet["frame"] == frame, "lamp packet frame mismatch")
    require(packet["official_head_id"] == site["official_head_id"], "lamp packet head mismatch")
    require(packet["facing_approach_id"] == site["ego_approach_id"], "lamp packet approach mismatch")
    aspects = packet["lit_aspects"]
    require(isinstance(aspects, list) and len(aspects) == len(set(aspects)), "invalid lamp aspects")
    require(all(isinstance(a, str) and a for a in aspects), "invalid lamp aspect")
    return packet


def run_native_attempt(site, source_root, world, actors, controller, lamp_ref_for_frame,
                       lawful_use_ref_for_frame, output_dir, case_id, frames):
    """Drive and retain original frames; caller owns actor cleanup.

    ``controller`` applies control before each tick. ``lamp_ref_for_frame``
    returns a path/hash reference to an original frame-specific observation.
    ``lawful_use_ref_for_frame`` returns a path/hash reference for each other
    participant, or None when no participant exists.
    """
    check_site(site, source_root)
    settings = world.get_settings()
    require(settings.synchronous_mode is True, "Native world must be synchronous")
    require(abs(float(settings.fixed_delta_seconds) - 0.05) < 1e-9, "Native tick must be 20 Hz")
    require(isinstance(frames, int) and frames >= 3, "insufficient original frames")
    require(case_id.startswith("testing__C111125__NRS-484B-307-3a__motor_vehicle_driver__"), "wrong exact case")
    require(len(actors) in (1, 2), "expected ego and optional other user")
    ego = actors[0]
    rows = []
    previous_frame = None
    previous_time = None
    for index in range(frames):
        controller(ego, index)
        frame = world.tick()
        snapshot = world.get_snapshot()
        elapsed = float(snapshot.timestamp.elapsed_seconds)
        require(snapshot.frame == frame, "Native snapshot frame mismatch")
        if previous_frame is not None:
            require(frame == previous_frame + 1, "Native frame gap")
            require(abs(elapsed - previous_time - 0.05) <= 1e-4, "Native timestamp gap")
        previous_frame, previous_time = frame, elapsed
        lamp_ref = lamp_ref_for_frame(frame)
        packet = _packet(source_root, lamp_ref, frame, site)
        pose = ego.get_location()
        require(all(math.isfinite(float(v)) for v in (pose.x, pose.y)), "nonfinite ego pose")
        users = []
        if len(actors) == 2:
            other = actors[1]
            other_pose = other.get_location()
            kind = site["other_user_kind"]
            require(kind in ("pedestrian", "motor_vehicle"), "other user kind absent")
            lawful_ref = lawful_use_ref_for_frame(frame, str(other.id))
            lawful_path = read_source(source_root, lawful_ref)
            lawful_packet = json.loads(lawful_path.read_text(encoding="utf-8"))
            require(lawful_packet["frame"] == frame and str(lawful_packet["user_id"]) == str(other.id), "lawful-use packet identity mismatch")
            require(all(math.isfinite(float(v)) for v in (other_pose.x, other_pose.y)), "nonfinite other pose")
            users.append({"id": str(other.id), "kind": kind, "xy": [other_pose.x, other_pose.y],
                          "lawful_use_source": lawful_ref["path"], "lawful_use_sha256": lawful_ref["sha256"]})
        rows.append({"frame": frame, "elapsed_seconds": elapsed,
                     "official_head_id": site["official_head_id"],
                     "facing_approach_id": site["ego_approach_id"],
                     "aspect_observation_source": lamp_ref["path"],
                     "aspect_observation_sha256": lamp_ref["sha256"],
                     "lit_aspects": packet["lit_aspects"],
                     "ego_xy": [pose.x, pose.y], "other_users": users})
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    event_path = output / "original-events.json"
    event_path.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    event_ref = {"path": event_path.name, "sha256": hashlib.sha256(event_path.read_bytes()).hexdigest()}
    receipt = {"case_id": case_id, "event_source": event_ref, "frame_count": len(rows),
               "first_frame": rows[0]["frame"], "last_frame": rows[-1]["frame"],
               "sample_hz": 20, "physical_acceptance_claimed": False,
               "permission_verdict": None, "right_of_way_verdict": None}
    (output / "native-attempt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt
