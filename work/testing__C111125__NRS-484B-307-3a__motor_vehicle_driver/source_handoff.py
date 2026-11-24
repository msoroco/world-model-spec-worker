"""Validate independently retained per-frame dual-aspect source references.

This is a saved-source custody check. A future live Native observer still must
collect original packets while ticking; a prewritten manifest is not evidence
that a local CARLA head actually displayed a simultaneous arrow lamp.
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, UnidentifiedImageError

from dual_green import check_site, read_source, require


def load_handoff(path, source_root, site, case_id, expected_frames=900,
                 diagnostic_fixture=False):
    check_site(site, source_root)
    root = Path(source_root)
    handoff = json.loads(Path(path).read_text(encoding="utf-8"))
    require(handoff.get("format") == "dual-green-original-source-handoff",
            "wrong original source handoff format")
    require(handoff.get("case_id") == case_id, "original source handoff case mismatch")
    require(handoff.get("official_head_id") == site["official_head_id"] and
            handoff.get("facing_approach_id") == site["ego_approach_id"],
            "original source handoff signal identity mismatch")
    methods = ("independent_camera_frame_review", "independent_physical_lamp_sensor")
    if diagnostic_fixture:
        methods += ("synthetic_diagnostic",)
    require(handoff.get("observer_method") in methods,
            "independent original lamp observer missing")
    frames = handoff.get("frames")
    require(isinstance(frames, list) and len(frames) == expected_frames,
            "incomplete original source handoff")
    lamps = {}
    lawful = {}
    prior = None
    for row in frames:
        frame = row.get("carla_frame")
        require(type(frame) is int and (prior is None or frame == prior + 1),
                "original source handoff frame gap")
        prior = frame
        lamp_ref = row.get("lamp")
        require(isinstance(lamp_ref, dict), "original lamp source reference missing")
        lamp = json.loads(read_source(root, lamp_ref).read_text(encoding="utf-8"))
        require(lamp.get("frame") == frame and
                lamp.get("official_head_id") == site["official_head_id"] and
                lamp.get("facing_approach_id") == site["ego_approach_id"],
                "original lamp packet does not match frame or official head")
        require(sorted(lamp.get("lit_aspects", [])) == sorted(
            ("circular_green", "green_" + site["arrow_direction"] + "_arrow")),
            "original lamp packet lacks simultaneous dual green")
        observed_ref = lamp.get("original_observation")
        require(isinstance(observed_ref, dict), "original lamp observation missing")
        observed = read_source(root, observed_ref)
        if diagnostic_fixture and observed.suffix.lower() == ".json":
            require(handoff["observer_method"] == "synthetic_diagnostic",
                    "synthetic lamp requires diagnostic observer method")
            marker = json.loads(observed.read_text(encoding="utf-8"))
            require(marker.get("format") == "synthetic-dual-green-lamp-observation" and
                    marker.get("frame") == frame and
                    marker.get("physical_observation") is False,
                    "invalid synthetic lamp observation")
        else:
            require(observed.suffix.lower() == ".png", "lamp observation must be original PNG")
            try:
                with Image.open(observed) as image:
                    require(image.format == "PNG" and image.width > 0 and image.height > 0,
                            "invalid original lamp observation")
                    image.load()
            except (OSError, UnidentifiedImageError) as error:
                raise ValueError("invalid original lamp observation") from error
        lamps[frame] = lamp_ref
        users = row.get("lawful_use", {})
        require(isinstance(users, dict), "original lawful-use references malformed")
        for user_id, ref in users.items():
            require(user_id and isinstance(ref, dict), "original lawful-use reference missing")
            packet = json.loads(read_source(root, ref).read_text(encoding="utf-8"))
            require(packet.get("frame") == frame and str(packet.get("user_id")) == user_id,
                    "original lawful-use packet identity mismatch")
            lawful[(frame, user_id)] = ref
    return {
        "lamp_ref_for_frame": lambda frame: lamps[frame],
        "lawful_use_ref_for_frame": lambda frame, user_id: lawful[(frame, user_id)],
        "first_frame": frames[0]["carla_frame"],
        "last_frame": frames[-1]["carla_frame"],
        "frame_count": len(frames),
    }
