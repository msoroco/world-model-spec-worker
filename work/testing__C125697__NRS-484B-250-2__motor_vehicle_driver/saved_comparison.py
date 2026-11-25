"""Independently audit source-sealed NRS 484B.250(2) exact comparisons."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import entry_timing
import median_source


AID = "testing__C125697__NRS-484B-250-2__motor_vehicle_driver"
COMPARISONS = {
    "left_approach_entry_timing_training_range": (
        "entry_timing", ("timing_below_training", "timing_inside_training",
                         "timing_above_training")),
    "entry_side_relation": (
        "approach_side", ("timing_inside_training", "right_approach_inside")),
}


def _source(root, name):
    candidate = root / name
    path = candidate.resolve()
    if candidate.is_symlink() or not path.is_relative_to(root) or not path.is_file():
        raise ValueError("missing original comparison source: " + name)
    return path


def audit(comparison_id, attempts, *, diagnostic=False):
    if comparison_id not in COMPARISONS:
        raise ValueError("unknown exact comparison")
    variable, suffixes = COMPARISONS[comparison_id]
    if len(attempts) != len(suffixes):
        raise ValueError("exact comparison member count required")
    cases = [AID + "__" + suffix for suffix in suffixes]
    observations = []
    scenes = []
    sources = []
    for attempt, case in zip(attempts, cases):
        root = Path(attempt).resolve()
        manifest_path = _source(root, "original-source-manifest.json")
        scene_path = _source(root, "scene.json")
        manifest = json.loads(manifest_path.read_text())
        scene = json.loads(scene_path.read_text())
        if manifest.get("case_id") != case or scene.get("case_id") != case:
            raise ValueError("wrong exact comparison case or order")
        if diagnostic:
            provenance = json.loads(_source(root, "fixture-provenance.json").read_text())
            if provenance.get("diagnostic_fixture") is not True or (
                    provenance.get("physical_acceptance_claimed") is not False):
                raise ValueError("diagnostic fixture provenance missing")
        else:
            seal = json.loads(_source(root, "capture-seal.json").read_text())
            if (seal.get("provenance_kind") != "native" or
                    seal.get("diagnostic_fixture") is not False or
                    seal.get("frames") != 900 or
                    seal.get("restoration", {}).get("restored") is not True):
                raise ValueError("original Native capture seal required")
            sealed = seal.get("sources", {})
            for name in ("scene.json", "original-source-manifest.json", "native_trace.json",
                         "opendrive.xodr", "device_inventory.json", "highway_identity.json",
                         "overview.mkv", "approach.mkv", "reference_corner.mkv",
                         "driver_reference.mkv"):
                path = _source(root, name)
                if sealed.get(name) != hashlib.sha256(path.read_bytes()).hexdigest():
                    raise ValueError("original Native source changed after seal: " + name)
        audited = median_source.audit_saved_sources(root, manifest, scene,
                                                    diagnostic_fixture=diagnostic)
        observation = audited["observations"]
        observation["source"] = {
            "path": str(_source(root, manifest["sources"]["native_trace"]["path"])),
            "sha256": audited["source_sha256"]["native_trace"]}
        observations.append(observation)
        scenes.append(scene)
        sources.append({"manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
                        "scene_sha256": hashlib.sha256(scene_path.read_bytes()).hexdigest(),
                        "original_sources": audited["source_sha256"]})
    fixed = ("crossing", "governing_signal", "ego_blueprint", "other_blueprint",
             "subsection_4_applicability_review", "opposing_left_turn_excluded_source")
    for field in fixed:
        if any(scene.get(field) != scenes[0].get(field) for scene in scenes):
            raise ValueError("comparison fixed condition changed: " + field)
    for name in ("opendrive", "device_inventory"):
        if any(source["original_sources"][name] != sources[0]["original_sources"][name]
               for source in sources):
            raise ValueError("comparison fixed source changed: " + name)
    if variable == "entry_timing":
        for field in ("ego_route_xy_m", "other_route_xy_m", "ego_highway",
                      "other_highway", "ego_approach_road_id", "other_approach_road_id"):
            if any(scene.get(field) != scenes[0].get(field) for scene in scenes):
                raise ValueError("timing comparison fixed condition changed: " + field)
    else:
        if scenes[0]["ego_route_xy_m"] != scenes[1]["other_route_xy_m"] or (
                scenes[0]["other_route_xy_m"] != scenes[1]["ego_route_xy_m"]):
            raise ValueError("side comparison did not swap original routes")
        if scenes[0]["ego_highway"] != scenes[1]["other_highway"] or (
                scenes[0]["other_highway"] != scenes[1]["ego_highway"]):
            raise ValueError("side comparison did not swap original highway roles")
        if scenes[0].get("requested_entry_offset_s") != scenes[1].get("requested_entry_offset_s"):
            raise ValueError("side comparison changed requested timing")
    compared = entry_timing.compare(observations, cases, variable)
    return {"comparison_id": comparison_id, "case_ids": cases, "variable": variable,
            "source_sha256": sources, "comparison": compared,
            "diagnostic_fixture": diagnostic, "physical_pixels_reviewed": False,
            "legal_applicability": "unresolved"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison-id", required=True, choices=tuple(COMPARISONS))
    parser.add_argument("--attempt", action="append", type=Path, required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    receipt = audit(args.comparison_id, args.attempt, diagnostic=args.diagnostic)
    args.output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"comparison_id": receipt["comparison_id"], "source_bound": True}))


if __name__ == "__main__":
    main()
