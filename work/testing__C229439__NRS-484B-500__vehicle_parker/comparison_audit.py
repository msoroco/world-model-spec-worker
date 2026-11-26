"""Independent source-bound checks for the three planned parking comparisons.

This checks measurement isolation and missing evidence. It does not decide the
legal characterization of a device, place, or person's conduct.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from parking_place import ASSIGNMENT, measure


CASES = {
    "park_inside_hazard": ("park", "inside", "hazardous"),
    "park_outside_hazard": ("park", "outside", "hazardous"),
    "stand_inside_hazard": ("stand", "inside", "hazardous"),
    "stop_inside_hazard": ("stop", "inside", "hazardous"),
    "park_inside_congested": ("park", "inside", "congested"),
}
COMPARISONS = {
    "inside_vs_outside": ("park_inside_hazard", "park_outside_hazard"),
    "stop_stand_park": ("park_inside_hazard", "stand_inside_hazard", "stop_inside_hazard"),
    "hazard_vs_congestion": ("park_inside_hazard", "park_inside_congested"),
}


def _load(path):
    path = Path(path)
    data = path.read_bytes()
    return json.loads(data), {"path": str(path), "sha256": hashlib.sha256(data).hexdigest()}


def audit(comparison_id: str, source_paths: dict[str, str | Path]) -> dict:
    if comparison_id not in COMPARISONS:
        raise ValueError("unknown exact comparison")
    names = COMPARISONS[comparison_id]
    if set(source_paths) != set(names):
        raise ValueError("missing or extra exact comparison evidence")
    rows = {}
    for name in names:
        packet, source = _load(source_paths[name])
        conduct, footprint, context = CASES[name]
        if (packet.get("assignment_id") != ASSIGNMENT
                or packet.get("case_id") != ASSIGNMENT + "__" + name
                or packet.get("requested_conduct") != conduct
                or packet.get("requested_footprint") != footprint
                or packet.get("place_context_for_review") != context):
            raise ValueError("case identity or planned contrast differs")
        construction = packet.get("construction")
        measurement = packet.get("measurement")
        if not isinstance(construction, dict) or not isinstance(measurement, dict):
            raise ValueError("original construction and measurement required")
        if (construction.get("assignment_id") != ASSIGNMENT
                or measurement.get("assignment_id") != ASSIGNMENT
                or construction.get("device_id") != measurement.get("device_id")
                or construction.get("designated_place_id") != measurement.get("designated_place_id")):
            raise ValueError("construction and measurement source identity differs")
        observations = measurement.get("observations")
        if not isinstance(observations, list) or len(observations) < 3:
            raise ValueError("original measured footprint history required")
        if not all("body_wholly_within_place" in o and "body_wholly_outside_place" in o
                   and "speed_mps" in o for o in observations):
            raise ValueError("original body and halt observations missing")
        stationary = [o for o in observations if o["speed_mps"] <= 0.1]
        if not stationary:
            raise ValueError("no measured stationary episode")
        if footprint == "inside" and not any(o["body_wholly_within_place"] for o in stationary):
            raise ValueError("inside body footprint absent during halt")
        if footprint == "outside" and not any(o["body_wholly_outside_place"] for o in stationary):
            raise ValueError("outside body footprint absent during halt")
        for field in ("official_authority_source", "loading_activity_source",
                      "officer_or_device_direction_source", "original_trace_id"):
            if not measurement.get(field):
                raise ValueError("missing original context source: " + field)
        rows[name] = {"packet": packet, "source": source}

    def values(field):
        return [rows[name]["packet"][field] for name in names]

    for field in ("vehicle_blueprint", "device_id", "designated_place_id",
                  "camera_plan_sha256", "duration_s", "rate_hz"):
        if any(not row["packet"].get(field) for row in rows.values()) or len(set(values(field))) != 1:
            raise ValueError("fixed comparison condition differs: " + field)
    if comparison_id == "inside_vs_outside":
        for field in ("requested_conduct", "place_context_for_review", "conduct_source_sha256",
                      "place_context_source_sha256"):
            if len(set(values(field))) != 1:
                raise ValueError("fixed comparison condition differs: " + field)
    elif comparison_id == "stop_stand_park":
        for field in ("requested_footprint", "place_context_for_review",
                      "place_context_source_sha256", "parking_pose_sha256"):
            if len(set(values(field))) != 1:
                raise ValueError("fixed comparison condition differs: " + field)
        if len(set(values("conduct_source_sha256"))) != len(names):
            raise ValueError("separate conduct sources required")
    else:
        for field in ("requested_footprint", "requested_conduct", "parking_pose_sha256",
                      "conduct_source_sha256"):
            if len(set(values(field))) != 1:
                raise ValueError("fixed comparison condition differs: " + field)
        if len(set(values("place_context_source_sha256"))) != len(names):
            raise ValueError("separate place-context sources required")
    return {"format": "worker-comparison-audit", "assignment_id": ASSIGNMENT,
            "comparison_id": comparison_id, "passed": True,
            "inputs": {name: rows[name]["source"] for name in names},
            "limit": "Measured isolation only; official status, place character, conduct and actual pixels require independent review."}


def audit_saved(comparison_id: str, analysis_roots: dict[str, str | Path], scratch: str | Path) -> dict:
    """Reconstruct comparison packets from saved reports and verified Native sources."""
    if comparison_id not in COMPARISONS or set(analysis_roots) != set(COMPARISONS[comparison_id]):
        raise ValueError("missing or extra exact saved comparison evidence")
    packets = {}
    source_bindings = {}
    fixture_only = False
    with tempfile.TemporaryDirectory(dir=scratch) as directory:
        for name, root in analysis_roots.items():
            root = Path(root)
            report, report_source = _load(root / "analysis-report.json")
            config, config_source = _load(root / "config.json")
            context, context_source = _load(root / "parking-context.json")
            acquisition, acquisition_source = _load(root / "acquisition.json")
            provenance_path = root / "acquisition-provenance.json"
            if not provenance_path.is_file():
                provenance_path = root / "fixture-provenance.json"
            provenance, provenance_source = _load(provenance_path)
            value = report["measurements"]["designated_parking_measurement"]["value"]
            measurement_input, measurement_input_source = _load(root / "parking-measurement-input.json")
            if (config.get("selected_case_id") != ASSIGNMENT + "__" + name or
                    value.get("case_id") != config["selected_case_id"] or
                    context.get("case_id") != config["selected_case_id"]):
                raise ValueError("saved report exact case identity differs")
            for filename, digest in value["sources"].items():
                source = root / filename
                if (not source.is_file() or hashlib.sha256(source.read_bytes()).hexdigest() != digest or
                        acquisition.get(filename, {}).get("sha256") != digest or
                        acquisition.get(filename, {}).get("kind") != "original_native"):
                    raise ValueError("saved comparison original source hash differs: " + filename)
            if value["source_context"] != context:
                raise ValueError("saved report context differs from original source")
            if (measurement_input.get("original_trace_id") != value["sources"]["parking-history.jsonl"] or
                    measure(root / "parking-measurement-input.json")["observations"] !=
                    value["body_observations"]):
                raise ValueError("saved comparison measurements differ from original body source")
            if provenance.get("provenance_kind") != "native" or provenance.get("diagnostic_fixture"):
                fixture_only = True
            case = config["case"]
            construction, construction_source = _load(root / "construction.json")
            camera_plan = json.dumps(config["cameras"], sort_keys=True).encode()
            pose = json.dumps(context["designated_place_polygon"], sort_keys=True).encode()
            context_source_key = (context["hazard_or_congestion_status"] + ":" +
                                  context["place_feature"]).encode()
            conduct_source_key = case["requested_conduct"].encode()
            packet = {"assignment_id": ASSIGNMENT, "case_id": config["selected_case_id"],
                "requested_conduct": case["requested_conduct"],
                "requested_footprint": case["requested_footprint"],
                "place_context_for_review": case["place_context_for_review"],
                "vehicle_blueprint": config.get("vehicle_blueprint_id", "vehicle.tesla.model3"),
                "device_id": context["device_id"],
                "designated_place_id": context["designated_place_id"],
                "camera_plan_sha256": hashlib.sha256(camera_plan).hexdigest(),
                "duration_s": config["duration_s"], "rate_hz": config["rate_hz"],
                "conduct_source_sha256": hashlib.sha256(conduct_source_key).hexdigest(),
                "place_context_source_sha256": hashlib.sha256(context_source_key).hexdigest(),
                "parking_pose_sha256": hashlib.sha256(pose).hexdigest(),
                "construction": {"assignment_id": ASSIGNMENT,
                                 "device_id": context["device_id"],
                                 "designated_place_id": context["designated_place_id"]},
                "measurement": {"assignment_id": ASSIGNMENT,
                                "device_id": context["device_id"],
                                "designated_place_id": context["designated_place_id"],
                                "observations": value["body_observations"],
                                "official_authority_source": context["official_authority_source"],
                                "loading_activity_source": context["loading_activity_source"],
                                "officer_or_device_direction_source": context["officer_or_device_direction_source"],
                                "original_trace_id": value["sources"]["parking-history.jsonl"]}}
            packet_path = Path(directory) / (name + ".json")
            packet_path.write_text(json.dumps(packet, allow_nan=False) + "\n", encoding="utf-8")
            packets[name] = packet_path
            source_bindings[name] = {"report": report_source, "config": config_source,
                "context": context_source, "acquisition": acquisition_source,
                "provenance": provenance_source, "construction": construction_source,
                "original_sources": value["sources"],
                "measurement_input": measurement_input_source}
        result = audit(comparison_id, packets)
    result["inputs"] = source_bindings
    result["fixture_only"] = fixture_only
    result["physical_acceptance_claimed"] = False
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison", choices=COMPARISONS, required=True)
    parser.add_argument("--input", action="append", nargs=2, metavar=("CASE_SUFFIX", "PACKET"), required=True)
    args = parser.parse_args(argv)
    paths = dict(args.input)
    if len(paths) != len(args.input):
        raise ValueError("duplicate exact comparison evidence")
    print(json.dumps(audit(args.comparison, paths), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
