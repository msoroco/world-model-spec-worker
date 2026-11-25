"""Materialize four exact inline CPU constructions from this source tree.

This builder operates only under its owning assignment directory. It embeds
source text so the current runtime can check byte identity after materializing.
"""
from __future__ import annotations

import json
from pathlib import Path

from opposing_pass import VARIANTS

HERE = Path(__file__).resolve().parent
ASSIGNMENT = "testing__C125714__NRS-484B-203-1__motor_vehicle_driver"
FILES = ("runner.py", "native_session.py", "native_history.py", "opposing_pass.py",
         "analysis.py", "physical_completion.py",
         "carla_adapter.py", "media_encode.py", "config.json", "tests/test_bundle_smoke.py")


def config(variant):
    if variant not in VARIANTS:
        raise ValueError("unknown exact opposing-pass case")
    return {
        "law_id": "NRS-484B-203-1", "cell_id": "C125714",
        "actor": "motor_vehicle_driver", "assignment_id": ASSIGNMENT,
        "selected_case_id": ASSIGNMENT + "__" + variant, "variant": variant,
        "supported_case_ids": [ASSIGNMENT + "__" + name for name in VARIANTS],
        "rate_hz": 20, "duration_s": 45,
        "cameras": [{"name": name, "width": width, "height": height}
            for name, width, height in (("overview", 1920, 1080), ("approach", 1280, 720),
                ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))],
        "recording_description": {
            "channels": [{"name": "opposing_actor_body_history", "unit": "metres and seconds",
                "sampling_rate_hz": 20, "method": "Original Native eight-vertex actor bodies, velocities and world clock",
                "time_window": "all 900 original world ticks", "reference_frame": "source-reviewed road station and lateral axes",
                "uncertainty": "body projection and source geometry require independent physical review"},
                {"name": "four_camera_views", "unit": "PNG frame",
                 "sampling_rate_hz": 20, "method": "Four original sensor frames joined to each Native tick",
                 "time_window": "all 900 original world ticks", "reference_frame": "same-frame Native sensor clocks",
                 "uncertainty": "pixel content and camera visibility require independent physical review"}],
            "context_inputs": [{"name": "reviewed_median_opening_map", "unit": "source packet",
                "method": "Separate original Native map review and live OpenDRIVE hash match"}],
            "limitations": ["No reviewed original site is supplied with this worker package.",
                "Observed actor bodies and pixels require local physical review; legal judgment unresolved."]},
        "physical_completion": {"format": "worker-physical-completion-criteria",
            "criterion": "opposing_pass", "motion_source": "opposing-actor-trace.json",
            "minimum_samples": 900, "minimum_passing_frames": 2,
            "engineering_tolerances_not_legal": True}
    }


def construction(variant, directory):
    cfg = config(variant)
    files = []
    for relative in FILES:
        source = (directory / relative) if relative == "config.json" else HERE / relative
        files.append({"path": relative, "content": source.read_text(encoding="utf-8")})
    return {"law_id": cfg["law_id"], "cell_id": cfg["cell_id"],
        "actor": cfg["actor"], "case_id": cfg["selected_case_id"],
        "entrypoint": "runner.py", "files": files,
        "recording_description": cfg["recording_description"],
        "measurement_plan": {"opposing_travel": "Original per-frame body velocities in surveyed road frame",
            "passing_side": "Direction-relative lateral body envelopes during longitudinal overlap",
            "half_paved": "Body envelopes against reviewed paved midpoint, without legal cutoff"},
        "mechanisms": ["SHA-sealed reviewed site and live OpenDRIVE match",
            "Owned two-actor opposing route control", "Four same-tick original RGB sensor views",
            "900-frame original body trace and saved pixel decode"],
        "static_checks": ["Exact case/config scope", "Source gate before world mutation",
            "Original frame and sensor timestamp join", "Owned cleanup/readback"],
        "termination_rules": ["900 original 20 Hz frames, or fail closed on stale source/time",
            "Actual physical pass remains subject to independent local audit"]}


def write():
    for variant in VARIANTS:
        directory = HERE if variant == VARIANTS[0] else HERE / "cases" / variant
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "config.json").write_text(
            json.dumps(config(variant), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (directory / "construction.json").write_text(
            json.dumps(construction(variant, directory), indent=2, sort_keys=True) + "\n",
            encoding="utf-8")


if __name__ == "__main__":
    write()
