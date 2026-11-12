"""Construct the untested crest-approach and reverse-occlusion site alternatives.

These are diagnostic construction packets. Their coordinates are engineering
plans, not surveyed Native map geometry or measurements of driver visibility.
"""

import copy
import hashlib
import json
import math
from pathlib import Path

from site_construction import _segment_intersects_box, validate_site

HERE = Path(__file__).resolve().parent
BASE = HERE / "diagnostic-site-crest-short.json"
OUT = HERE / "branch-sites"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def grade(x):
    """Eight metre triangular crest, extended to the 200 m approach station."""
    return max(0.0, 8.0 - abs(x) * 0.05)


def _place_occluder(site, direction):
    turn = site["turn_site_xyz_m"]
    station = site["incoming_lanes"][direction]["stations"][-1]["xyz_m"]
    # The prop is placed inside the 500-foot probe, on this direction's
    # planned eye-to-body ray. This does not predict a real CARLA sight result.
    # The short-probe ray packet first samples occlusion at 150 m. With the
    # two-metre x half extent, put the planned prop's near face at that station.
    fraction = (150.0 + 2.0) / station_distance(site, direction)
    eye = [station[0], station[1], station[2] + 1.4]
    body = [turn[0], turn[1], turn[2] + 1.5]
    center = [body[i] + fraction * (eye[i] - body[i]) for i in range(3)]
    site["occluder"] = {
        "blueprint_id": "static.prop.fixture_wall",
        "center_xyz_m": center,
        "half_extent_xyz_m": [2, 2, 2],
        "yaw_deg": 0,
        "target_direction": direction,
    }


def station_distance(site, direction):
    return site["incoming_lanes"][direction]["stations"][-1]["distance_to_turn_m"]


def construct(base, placement, direction):
    if placement not in ("near_summit", "approach_to_crest") or direction not in ("approach_a", "approach_b"):
        raise ValueError("Unknown statutory alternative")
    site = copy.deepcopy(base)
    site["source_status"] = "diagnostic_fixture"
    site["map_name"] = "SyntheticCrestBranchPlan"
    site["centerline_xyz_m"] = [[-220, 0, grade(-220)], [0, 0, grade(0)],
                                 [220, 0, grade(220)]]
    turn_x = -40 if placement == "approach_to_crest" else 0
    site["turn_site_xyz_m"] = [turn_x, 0, grade(turn_x)]
    for sign, name in ((-1, "approach_a"), (1, "approach_b")):
        for station in site["incoming_lanes"][name]["stations"]:
            x = turn_x + sign * station["distance_to_turn_m"]
            station["xyz_m"] = [x, 0, grade(x)]
    # Preserve the same U-turn form, moving it to the new site. Its sampled
    # z coordinates follow the planned grade, including lateral route points.
    for point in site["u_turn_route_xyz_m"]:
        point[0] += turn_x
        point[2] = grade(point[0])
    for pose in site["camera_poses"].values():
        pose[0] += turn_x
        pose[2] += grade(turn_x) - 8
    _place_occluder(site, direction)
    validate_site(site)
    if placement == "approach_to_crest" and not (site["turn_site_xyz_m"][0] < 0 and
                                                    site["turn_site_xyz_m"][2] < grade(0)):
        raise ValueError("Turn site is not on the approach to the summit")
    if placement == "near_summit" and site["turn_site_xyz_m"][0] != 0:
        raise ValueError("Near-summit site moved away from summit")
    return site


def check_branch(site, placement, direction):
    validate_site(site)
    if site["source_status"] != "diagnostic_fixture":
        raise ValueError("Unreviewed geometry cannot claim Native source status")
    if site["occluder"]["target_direction"] != direction:
        raise ValueError("Wrong occluded direction")
    turn_x = site["turn_site_xyz_m"][0]
    if (placement == "approach_to_crest") != (turn_x < 0 and grade(turn_x) < grade(0)):
        raise ValueError("Wrong crest placement")
    center = site["occluder"]["center_xyz_m"]
    extent = site["occluder"]["half_extent_xyz_m"]
    turn = site["turn_site_xyz_m"]
    if site["probe"] == "short_of_500ft" and not math.isclose(
            abs(center[0] - turn[0]) - extent[0], 150.0, abs_tol=1e-7):
        raise ValueError("Planned prop near face differs from short-probe ray station")
    target = [turn[0], turn[1], turn[2] + 1.5]
    observed = {}
    for name, lane in site["incoming_lanes"].items():
        far = lane["stations"][-1]["xyz_m"]
        eye = [far[0], far[1], far[2] + 1.4]
        observed[name] = _segment_intersects_box(eye, target, center, extent, 0)
    if not observed[direction] or observed["approach_b" if direction == "approach_a" else "approach_a"]:
        raise ValueError("Prop must cross only the selected direction's planned ray")
    return {"turn_site_to_summit_m": abs(turn_x), "planned_ray_crossings": observed,
            "approach_stations_m": {name: [row["distance_to_turn_m"] for row in lane["stations"]]
                                    for name, lane in site["incoming_lanes"].items()}}


def main():
    base = json.loads(BASE.read_text())
    OUT.mkdir(exist_ok=True)
    rows = []
    for placement in ("near_summit", "approach_to_crest"):
        for direction in ("approach_a", "approach_b"):
            site = construct(base, placement, direction)
            check = check_branch(site, placement, direction)
            name = placement + "__occluded_" + direction
            path = OUT / (name + ".json")
            path.write_text(json.dumps(site, indent=2, sort_keys=True) + "\n")
            rows.append({"name": name, "path": str(path.relative_to(HERE)),
                         "sha256": digest(path), "check": check})
    report = {"kind": "cpu_diagnostic_branch_construction", "source_status": "diagnostic_fixture",
              "source": {"path": BASE.name, "sha256": digest(BASE)},
              "generator_sha256": digest(__file__), "alternatives": rows,
              "physical_acceptance_claimed": False}
    (OUT / "construction-proof.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"alternatives": len(rows), "approach_to_crest": 2,
                      "swapped_occlusion": 2, "physical_acceptance_claimed": False}))


if __name__ == "__main__":
    main()
