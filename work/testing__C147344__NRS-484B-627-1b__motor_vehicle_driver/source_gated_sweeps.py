"""Stage six reviewed-source engineering sweeps for the two judgment phrases.

Endpoints and spacing must come from original reviewed physical sources. The
three points are construction requests, never legal thresholds or realization.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from reviewed_scene import ASSIGNMENT, _linked, plan

AXES = {
    "impediment": ("slow_middle_follower", "ego_speed_mps", "ego"),
    "passing_necessity": ("slow_middle_passing", "slower_speed_mps", "slower_vehicle"),
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finite_positive(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value > 0


def prepare(authority_root: Path, site_ref: dict, ranges_ref: dict) -> dict:
    root = Path(authority_root).resolve()
    site_path = _linked(root, site_ref)
    site = json.loads(site_path.read_text(encoding="utf-8"))
    if site.get("reviewed_original_site") is not True or site.get("diagnostic_fixture") is True:
        raise ValueError("reviewed original highway site required")
    ranges_path = _linked(root, ranges_ref)
    ranges = json.loads(ranges_path.read_text(encoding="utf-8"))
    if (ranges.get("format") != "c147344-reviewed-sweep-ranges-v1" or
            ranges.get("reviewed_original_ranges") is not True or
            ranges.get("diagnostic_fixture") is True or
            ranges.get("site_sha256") != sha(site_path)):
        raise ValueError("original reviewed sweep ranges missing or stale")
    control_path = _linked(root, ranges.get("control_ref"))
    control = json.loads(control_path.read_text(encoding="utf-8"))
    if (control.get("reviewed_original_controls") is not True or
            control.get("diagnostic_fixture") is True or
            control.get("site_sha256") != sha(site_path)):
        raise ValueError("original reviewed numeric controls missing or stale")
    evidence = ranges.get("evidence_refs")
    if not isinstance(evidence, list) or not evidence:
        raise ValueError("original sweep feasibility evidence missing")
    evidence_hashes = []
    for ref in evidence:
        _linked(root, ref)
        evidence_hashes.append(ref["sha256"])
    definitions = ranges.get("axes")
    if not isinstance(definitions, dict) or set(definitions) != set(AXES):
        raise ValueError("both original judgment axes required")
    supported = control.get("supported_numeric_controls")
    if not isinstance(supported, list) or {x.get("name") for x in supported if isinstance(x, dict)} != \
            {item[1] for item in AXES.values()}:
        raise ValueError("both numeric actor controls need original source binding")
    bindings = {entry["name"]: entry for entry in supported}
    scenes = []
    for axis_name, (anchor, variable, role) in AXES.items():
        axis = definitions[axis_name]
        binding = bindings[variable]
        if (axis.get("variable") != variable or axis.get("unit") != "m/s" or
                binding.get("actor_role") != role or
                binding.get("original_readback_field") !=
                ("ego_speed_mps" if role == "ego" else "slower_vehicle_speed_mps") or
                not all(finite_positive(axis.get(key)) for key in ("minimum", "maximum", "spacing")) or
                axis["minimum"] >= axis["maximum"] or
                axis["spacing"] > axis["maximum"] - axis["minimum"] or
                not axis.get("range_rationale") or not axis.get("spacing_rationale") or
                not axis.get("feasibility_evidence")):
            raise ValueError("source-supported physical range/control invalid: " + axis_name)
        feasibility_ref = axis.get("feasibility_source_ref")
        _linked(root, feasibility_ref)
        if feasibility_ref["sha256"] not in evidence_hashes:
            raise ValueError("axis feasibility source omitted from evidence packet: " + axis_name)
        anchor_scene = plan(root, site_ref, ASSIGNMENT + "__" + anchor)
        points = (axis["minimum"], (axis["minimum"] + axis["maximum"]) / 2,
                  axis["maximum"])
        if points[1] - points[0] < axis["spacing"] or points[2] - points[1] < axis["spacing"]:
            raise ValueError("three source-spaced construction points unavailable")
        for label, value in zip(("minimum", "middle", "maximum"), points):
            scene = json.loads(json.dumps(anchor_scene))
            scene["case_id"] = ASSIGNMENT + "__" + axis_name + "_" + label
            target = next(actor for actor in scene["actors"] if actor["role"] == role)
            target["target_speed_mps"] = value
            scene["sweep"] = {"axis_id": axis_name, "anchor_case_id": anchor_scene["case_id"],
                              "variable": variable, "requested_setpoint": value,
                              "original_readback_field": binding["original_readback_field"],
                              "ranges_sha256": sha(ranges_path), "control_sha256": sha(control_path),
                              "feasibility_sha256": axis["feasibility_source_ref"]["sha256"],
                              "legal_threshold": None, "realized_value": None}
            scenes.append(scene)
    return {"format": "c147344-source-gated-sweep-scenes-v1", "assignment_id": ASSIGNMENT,
            "site_sha256": sha(site_path), "ranges_sha256": sha(ranges_path),
            "control_sha256": sha(control_path), "evidence_sha256": evidence_hashes,
            "scenes": scenes, "physical_acceptance": False, "legal_verdict": None}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority-root", type=Path, required=True)
    parser.add_argument("--site-ref", type=Path, required=True)
    parser.add_argument("--ranges-ref", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("retain prior reviewed sweep construction")
    packet = prepare(args.authority_root, json.loads(args.site_ref.read_text()),
                     json.loads(args.ranges_ref.read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(packet, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"case_ids": [scene["case_id"] for scene in packet["scenes"]],
                      "physical_acceptance": False}))


if __name__ == "__main__":
    main()
