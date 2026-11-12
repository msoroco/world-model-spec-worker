"""Bind source-backed engineering sweep points without legal or physical claims."""

import hashlib
import json
from pathlib import Path

from build_crest_opendrive import check_source_geometry as check_crest
from build_curve_opendrive import check_source_geometry as check_curve

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PROPOSALS = HERE / "proposals/cases.json"
PLAN = HERE / "case-plan.json"
PROBES = {"short_of_500ft": 150.0, "at_500ft": 152.4, "beyond_500ft": 160.0}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    plan = json.loads(PLAN.read_text())
    proposals = json.loads(PROPOSALS.read_text())
    proposed = {row["case_id"] for row in proposals["cases"]}
    points = []
    for row in plan["cases"]:
        case_id = row["case_id"]
        if "__occluded_" not in case_id:
            continue
        if case_id not in proposed:
            raise ValueError("Sweep case missing semantic proposal: " + case_id)
        name = row["diagnostic_manifest"].removeprefix("diagnostic-").removesuffix("-manifest.json")
        manifest = HERE / row["diagnostic_manifest"]
        entry = json.loads(manifest.read_text())["cases"][0]
        if entry["case_id"] != case_id or sha(HERE / entry["construction"]) != entry["construction_sha256"]:
            raise ValueError("Sweep case construction not current: " + case_id)
        feature, probe = row["feature"], row["probe"]
        if probe not in PROBES or feature not in ("curve", "crest"):
            raise ValueError("Unexpected sweep axis")
        direction = row["occluded_direction"]
        if direction not in ("approach_a", "approach_b"):
            raise ValueError("Unexpected sweep direction")
        if feature == "curve":
            suffix = {"short_of_500ft": "", "at_500ft": "-at", "beyond_500ft": "-beyond"}[probe]
            site_path = HERE / ("branch-proof-" + name) / ("diagnostic-site" + suffix + ".json")
            road = HERE / "native-map-plan/curve-road.xodr"
            check = check_curve
            placement = "on_curve"
        else:
            short = {"short_of_500ft": "short", "at_500ft": "at", "beyond_500ft": "beyond"}[probe]
            site_path = HERE / ("branch-proof-" + name) / ("diagnostic-site-crest-" + short + ".json")
            road = HERE / "native-map-plan/crest-road.xodr"
            check = check_crest
            placement = row["site_placement"]
        site = json.loads(site_path.read_text())
        build = json.loads((HERE / ("branch-proof-" + name) / "build-receipt.json").read_text())
        if (site["occluder"]["target_direction"] != direction or
                site["map_source"]["sha256"] != sha(road) or
                build["site_sha256"] != sha(site_path) or
                build["construction_sha256"] != entry["construction_sha256"]):
            raise ValueError("Sweep road/site/target direction changed: " + case_id)
        check(road.read_text(), site)
        points.append({
            "case_id": case_id, "feature": feature, "probe": probe,
            "engineering_probe_distance_m": PROBES[probe],
            "site_placement": placement, "occluded_direction": direction,
            "turn_site_xyz_m": site["turn_site_xyz_m"],
            "road_source": str(road.relative_to(HERE)), "road_sha256": sha(road),
            "site_source": str(site_path.relative_to(HERE)), "site_sha256": sha(site_path),
            "construction_sha256": entry["construction_sha256"],
            "physical_acceptance_claimed": False,
        })
    if len(points) != 18 or len({point["case_id"] for point in points}) != 18:
        raise ValueError("Expected twelve crest and six curve direction sweep points")
    for feature, count in (("curve", 6), ("crest", 12)):
        subset = [point for point in points if point["feature"] == feature]
        if len(subset) != count or {point["probe"] for point in subset} != set(PROBES):
            raise ValueError("Incomplete feature/boundary sweep: " + feature)
        for probe in PROBES:
            group = [point for point in subset if point["probe"] == probe]
            if {point["occluded_direction"] for point in group} != {"approach_a", "approach_b"}:
                raise ValueError("Missing approach direction: " + feature + "/" + probe)
            if feature == "crest" and {point["site_placement"] for point in group} != {
                    "near_summit", "approach_to_crest"}:
                raise ValueError("Missing crest placement: " + probe)
    source = json.loads((ROOT / "inputs" / HERE.name / "assignment.json").read_text())
    law = source["law"]["text"]
    if "either direction within 500 feet" not in law or "near the crest" not in law:
        raise ValueError("Frozen law text changed")
    sweep = {
        "sweep_id": "nrs-484b-407-driver-visibility",
        "target_law_id": source["law_id"],
        "status": "incomplete",
        "law_quote": law,
        "frozen_law_sha256": sha(ROOT / "inputs" / HERE.name / "assignment.json"),
        "judgment_refs": [
            {"phrase": "near the crest of a grade",
             "note": "No invented distance defines near; retain source geometry and pose."},
            {"phrase": "cannot be seen by the driver",
             "note": "Virtual eye rays are physical proxies; driver recognition is unresolved."},
        ],
        "rationale": "Source-bound CPU engineering samples retain both directions, three 500-foot probes and two crest placements without defining a legal judgment threshold.",
        "missing_inputs": ["Reviewed Native map, actor and camera evidence for physical sweep feasibility and driver recognition."],
        "engineering_axes": {
            "feature": ["curve", "crest"],
            "crest_site_placement": ["near_summit", "approach_to_crest"],
            "occluded_direction": ["approach_a", "approach_b"],
            "approach_probe_m": list(PROBES.values()),
        },
        "points": points,
        "physical_checks_pending": ["CARLA map and wall realization", "both approaching driver views",
                                    "actual actor visibility and camera pixels"],
        "legal_judgment_reserved": True,
        "physical_acceptance_claimed": False,
    }
    proposals["sweep_specs"] = [sweep]
    proposals["sweeps_expanded"] = True
    binding_path = HERE / "proposals/bindings.json"
    binding = json.loads(binding_path.read_text())
    for name, domain in (("site_placement", "on_curve, near_summit or approach_to_crest"),
                         ("occluded_direction", "approach_a or approach_b")):
        if not any(item["name"] == name for item in binding["variable_parameters"]):
            binding["variable_parameters"].append({
                "name": name, "kind": "world_setup", "range_or_domain": domain,
                "used_by_laws": [source["law_id"]]})
    for item in proposals["cases"]:
        assignments = item["variable_assignments"]
        if "site_placement" not in assignments:
            feature = assignments["feature"]["value"]
            assignments["site_placement"] = {"kind": "world_setup", "unit": "categorical",
                                             "value": "on_curve" if feature == "curve" else "near_summit"}
        if "occluded_direction" not in assignments:
            assignments["occluded_direction"] = {"kind": "world_setup", "unit": "categorical",
                                                 "value": "approach_a"}
    binding_path.write_text(json.dumps(binding, indent=2, sort_keys=True) + "\n")
    PROPOSALS.write_text(json.dumps(proposals, indent=2, sort_keys=True) + "\n")
    index_path = HERE / "proposals/semantic-index.json"
    index = json.loads(index_path.read_text())
    if index["stages"]["cases"]["path"] != "proposals/cases.json":
        raise ValueError("Semantic cases stage path changed")
    index["stages"]["cases"]["sha256"] = sha(PROPOSALS)
    index["stages"]["bindings"]["sha256"] = sha(binding_path)
    index_path.write_text(json.dumps(index, indent=2, sort_keys=True) + "\n")
    proof = {"format": "worker-judgment-sweep-cpu-proof", "sweep_id": sweep["sweep_id"],
             "point_count": len(points), "curve_points": 6, "crest_points": 12,
             "proposal_sha256": sha(PROPOSALS),
             "frozen_law_sha256": sweep["frozen_law_sha256"],
             "legal_judgment_reserved": True, "physical_acceptance_claimed": False}
    (HERE / "judgment-sweep-proof.json").write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")
    print(json.dumps(proof, sort_keys=True))


if __name__ == "__main__":
    main()
