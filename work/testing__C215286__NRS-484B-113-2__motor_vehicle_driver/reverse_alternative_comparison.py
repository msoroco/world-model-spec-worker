"""Independent source comparison for backing into vs stopping before a region."""

import argparse
import hashlib
import json
from pathlib import Path

from reverse_alternatives import analyze


ASSIGNMENT = "testing__C215286__NRS-484B-113-2__motor_vehicle_driver"
SUFFIXES = {
    "intersection": ("reverse_into_intersection", "reverse_stops_before_intersection"),
    "street_corner": ("reverse_around_street_corner", "reverse_stops_before_street_corner"),
}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(positive, stop_before, alternative):
    if alternative not in SUFFIXES:
        raise ValueError("Unknown backing comparison")
    roots = [Path(positive), Path(stop_before)]
    names = [ASSIGNMENT + "__" + suffix for suffix in SUFFIXES[alternative]]
    configs, sites, contexts, reports = [], [], [], []
    for root, case_id, expected in zip(roots, names, (True, False)):
        config = json.loads((root / "config.json").read_text())
        site_name = alternative + ("_site.json" if expected else "_stop_site.json")
        site = json.loads((root / site_name).read_text())
        context = json.loads((root / "reverse_site_context.json").read_text())
        if config.get("selected_case_id") != case_id:
            raise ValueError("Comparison case identity differs")
        if (site.get("alternative"), site.get("expected_entry")) != (alternative, expected):
            raise ValueError("Comparison site alternative differs")
        if context.get("site_packet_source") != {"path": site_name,
                                                  "sha256": _sha(root / site_name)}:
            raise ValueError("Original site packet source differs")
        if context.get("expected_entry") is not expected:
            raise ValueError("Original context comparison target differs")
        report = analyze(root, alternative)
        if len(report["samples"]) != 900:
            raise ValueError("Comparison requires 900 original 20 Hz frames")
        configs.append(config)
        sites.append(site)
        contexts.append(context)
        reports.append(report)
    for key in ("law_id", "cell_id", "actor", "rate_hz", "duration_s",
                "cameras", "required_atoms", "supported_case_ids"):
        if configs[0].get(key) != configs[1].get(key):
            raise ValueError("Comparison fixed capture condition differs: " + key)
    for key in ("native_map_id", "road_id", "region_polygon_xy_m",
                "vehicle_blueprint_id", "start_transform", "start_body_vertices_xy_m",
                "geometry_source", "camera_source", "road_topology_source"):
        if sites[0].get(key) != sites[1].get(key):
            raise ValueError("Comparison fixed site condition differs: " + key)
    if sites[0].get("route_xy_m") == sites[1].get("route_xy_m"):
        raise ValueError("Comparison reverse route does not differ")
    if reports[0]["reverse_body_enters_region"] is not True:
        raise ValueError("Positive reverse body did not enter selected region")
    if reports[1]["reverse_body_enters_region"] is not False:
        raise ValueError("Stop-before reverse body entered selected region")
    if alternative == "street_corner":
        if abs(reports[0]["heading_change_while_in_corner_deg"]) <= 0:
            raise ValueError("Positive reverse corner heading did not change")
        if abs(reports[1]["heading_change_while_in_corner_deg"]) > 0:
            raise ValueError("Stop-before corner case changed heading in region")
    return {
        "format": "worker-reverse-alternative-comparison",
        "alternative": alternative,
        "case_ids": names,
        "original_frames_per_case": 900,
        "fixed_conditions": ["law/cell/actor", "Native map/road/region and source hashes",
                             "start body/vehicle", "20 Hz, 45 seconds and four cameras"],
        "deliberate_difference": "reverse route stops before or enters selected region",
        "positive_source_sha256": reports[0]["source_sha256"],
        "stop_before_source_sha256": reports[1]["source_sha256"],
        "physical_acceptance_claimed": False,
        "legal_verdict_asserted": False,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--positive", required=True)
    parser.add_argument("--stop-before", required=True)
    parser.add_argument("--alternative", choices=tuple(SUFFIXES), required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = audit(args.positive, args.stop_before, args.alternative)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
