"""Independent saved-source audit of the ten exact parking comparisons."""

import argparse
import hashlib
import json
from pathlib import Path

from parking_measurements import ASSIGNMENT_ID, measure


ROOT = Path(__file__).resolve().parent
PLAN = json.loads((ROOT / "case-plan.json").read_text(encoding="utf-8"))
COMPARISONS = {row["comparison_id"]: tuple(cid.split("__")[-1] for cid in row["case_ids"])
               for row in PLAN["comparisons"]}
ALLOWED = {"device_permission": "requested_device", "permit_vs_restrict": "requested_device",
           "official_status": "requested_device", "park_vs_stand_permission": "requested_device",
           "standing_permission": "requested_device", "stand_vs_park_permission": "requested_device",
           "left_vs_right": "requested_side", "park_vs_stop": "requested_activity",
           "oneway_prerequisite": "requested_road_direction",
           "laned_prerequisite": "requested_marked_lane_count"}
SOURCES = ("parking-history.jsonl", "parking-context.json", "video_frames.jsonl", "trace.jsonl")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def audit_saved(comparison_id, roots):
    members = COMPARISONS.get(comparison_id)
    if members is None or set(roots) != set(members):
        raise ValueError("missing or extra exact comparison evidence")
    packets = {}
    fixture_only = False
    for suffix in members:
        root = Path(roots[suffix]).resolve()
        cfg = read(root / "config.json")
        report = read(root / "analysis-report.json")
        context = read(root / "parking-context.json")
        acquisition = read(root / "acquisition.json")
        measurement_receipt = root / "oneway-measurement-receipt.json"
        if (cfg.get("assignment_id") != ASSIGNMENT_ID or
                cfg.get("selected_case_id") != ASSIGNMENT_ID + "__" + suffix or
                context.get("case_id") != cfg["selected_case_id"]):
            raise ValueError("saved exact case or source context differs")
        for name in SOURCES:
            source = root / name
            if (not source.is_file() or acquisition.get(name, {}).get("kind") != "original_native"
                    or acquisition[name].get("sha256") != sha(source)):
                raise ValueError("saved original source missing or changed: " + name)
        receipt = read(measurement_receipt)
        fixture_only |= bool(receipt.get("diagnostic_fixture"))
        value = measure(cfg["selected_case_id"], root / "parking-context.json",
                        root / "parking-history.jsonl", measurement_receipt,
                        allow_diagnostic=bool(receipt.get("diagnostic_fixture")))
        observed = report.get("measurements", {}).get("oneway_parking_measurement", {}).get("value")
        if not isinstance(observed, dict) or any(observed.get(key) != value.get(key) for key in
                                              ("case_id", "source_bindings", "observations",
                                               "marked_lane_count", "one_way_restriction",
                                               "device_kind_source_label")):
            raise ValueError("saved parking measurement differs from original source")
        stationary = [row for row in value["observations"] if row["speed_mps"] <= .1]
        if not stationary:
            raise ValueError("measured stationary vehicle absent")
        packets[suffix] = {"config": cfg, "context": context,
                           "source": {"analysis_report": sha(root / "analysis-report.json"),
                                      "context": sha(root / "parking-context.json"),
                                      "parking_history": sha(root / "parking-history.jsonl"),
                                      "measurement_receipt": sha(measurement_receipt)},
                           "stationary": stationary}
    allowed = ALLOWED[comparison_id]
    keys = ("requested_side", "requested_activity", "requested_device",
            "requested_road_direction", "requested_marked_lane_count")
    cases = [packets[name]["config"]["case"] for name in members]
    for key in keys:
        values = [case[key] for case in cases]
        if key == allowed and len(set(values)) != len(values):
            raise ValueError("declared comparison variable did not vary: " + key)
        if key != allowed and len(set(values)) != 1:
            raise ValueError("fixed comparison condition differs: " + key)
    cfgs = [packets[name]["config"] for name in members]
    for key in ("cameras", "duration_s", "rate_hz", "actor", "law_id", "cell_id"):
        if any(cfg[key] != cfgs[0][key] for cfg in cfgs[1:]):
            raise ValueError("fixed capture or identity differs: " + key)
    contexts = [packets[name]["context"] for name in members]
    for key in ("map_sha256", "road_origin_xy", "road_forward_xy",
                "roadway_polygon_xy", "roadway_public_use_source", "roadway_boundary_source"):
        if any(context[key] != contexts[0][key] for context in contexts[1:]):
            raise ValueError("fixed original roadway source differs: " + key)
    if allowed == "requested_side":
        medians = [sum(row["leftward_min_m"] + row["leftward_max_m"] for row in packets[name]["stationary"])
                   / (2 * len(packets[name]["stationary"])) for name in members]
        if medians[0] * medians[1] >= 0:
            raise ValueError("original body side did not vary")
    return {"format": "worker-comparison-audit", "assignment_id": ASSIGNMENT_ID,
            "comparison_id": comparison_id, "passed": True,
            "declared_variable": allowed,
            "inputs": {name: packets[name]["source"] for name in members},
            "fixture_only": fixture_only, "physical_acceptance_claimed": False,
            "limit": "Measured isolation only; original device permission and legal conduct remain for independent review."}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--comparison", required=True, choices=sorted(COMPARISONS))
    parser.add_argument("--input", action="append", nargs=2, metavar=("CASE_SUFFIX", "SAVED_ROOT"), required=True)
    args = parser.parse_args(argv)
    roots = dict(args.input)
    if len(roots) != len(args.input):
        raise ValueError("duplicate comparison source")
    print(json.dumps(audit_saved(args.comparison, roots), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
