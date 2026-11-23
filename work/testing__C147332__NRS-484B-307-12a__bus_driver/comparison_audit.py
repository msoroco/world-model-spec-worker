"""Independent source-bound audit of the exact green-arrow comparisons."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from analysis import sha, verified_join
from green_lane_measurement import compare_green_indication, compare_permission_without_motion


CASES = {"adjacent_dark_drive", "second_green_drive",
         "green_selected_drive", "green_selected_stand"}


def case(attempt):
    path = Path(attempt) / "scene.json"
    scene = json.loads(path.read_text())
    suffix = scene.get("case_id", "").rsplit("__", 1)[-1]
    if suffix not in CASES or scene.get("law_id") != "NRS-484B-307-12a" or scene.get("cell_id") != "C147332":
        raise ValueError("unexpected exact comparison case")
    return suffix, scene, sha(path)


def audit(first_attempt, second_attempt, kind):
    if kind not in ("second_green_arrow", "permission_without_motion"):
        raise ValueError("unknown comparison")
    first, a_scene, a_sha = case(first_attempt)
    second, b_scene, b_sha = case(second_attempt)
    expected = (("adjacent_dark_drive", "second_green_drive") if kind == "second_green_arrow"
                else ("green_selected_drive", "green_selected_stand"))
    if (first, second) != expected:
        raise ValueError("wrong exact comparison case pair or order")
    fixed = ("assignment_id", "law_id", "cell_id", "actor", "layout", "control",
             "bus_blueprint_id", "map_source_sha256", "bus_lane_id", "bus_half_width_m")
    if any(a_scene.get(key) != b_scene.get(key) for key in fixed):
        raise ValueError("comparison changed fixed scene identity or geometry")
    if kind == "second_green_arrow" and a_scene.get("route_waypoint_centers_m") != b_scene.get("route_waypoint_centers_m"):
        raise ValueError("green-arrow comparison changed route request")
    if kind == "permission_without_motion" and a_scene.get("signals") != b_scene.get("signals"):
        raise ValueError("motion comparison changed signal request")
    a_frames, a_site = verified_join(first_attempt)
    b_frames, b_site = verified_join(second_attempt)
    if (a_site["highway_source_sha256"] != b_site["highway_source_sha256"] or
            a_site["official_device_source_sha256"] != b_site["official_device_source_sha256"]):
        raise ValueError("comparison changed reviewed highway or device source")
    if kind == "second_green_arrow":
        observed = compare_green_indication(a_frames, b_frames, a_scene["bus_lane_id"])
    else:
        observed = compare_permission_without_motion(a_frames, b_frames)
    return {"format": "worker-comparison-audit", "comparison": kind,
            "cases": [a_scene["case_id"], b_scene["case_id"]],
            "scene_sha256": [a_sha, b_sha], "reviewed_site_packet_sha256": [
                a_site["reviewed_packet_sha256"], b_site["reviewed_packet_sha256"]],
            "observations": observed, "source_bound": True,
            "physical_acceptance_claimed": False, "legal_verdict_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--first-attempt", required=True)
    parser.add_argument("--second-attempt", required=True)
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = audit(args.first_attempt, args.second_attempt, args.comparison)
    output = Path(args.output)
    if output.exists():
        raise ValueError("retain prior audit; choose a fresh output")
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
