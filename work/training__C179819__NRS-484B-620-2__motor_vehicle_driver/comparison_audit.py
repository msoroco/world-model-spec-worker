"""Independent source and fixed-condition audit for linked C179819 cases."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Missing source: " + path.name)
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(comparison_id, processing_specs, omit_case=None):
    plan = read(HERE / "case-plan.json")
    comparison = next((x for x in plan["comparisons"] if x["comparison_id"] == comparison_id), None)
    if comparison is None:
        raise ValueError("Unknown comparison")
    paths = dict(item.split("=", 1) for item in processing_specs)
    if set(paths) != set(comparison["case_ids"]) or omit_case:
        raise ValueError("Missing comparison case: " + str(omit_case or sorted(set(comparison["case_ids"]) - set(paths))))
    manifest = read(HERE / "execution-manifest.json")
    observations = []
    for case_id in comparison["case_ids"]:
        selected = next(x for x in manifest["cases"] if x["case_id"] == case_id)
        saved = read(paths[case_id])
        if (saved.get("passed") is not True or saved.get("recorded_only") is not True or
                saved.get("case_id") != case_id or saved.get("candidate_id") != "primary" or
                saved.get("native_revision", {}).get("construction_sha256") != selected["construction_sha256"] or
                saved.get("timestamp_joins", {}).get("frames") != 600):
            raise ValueError("Selected comparison source differs")
        stage = Path(saved["analysis_directory"])
        config = read(stage / "config.json")
        report = read(stage / "analysis-report.json")
        measured = report.get("measurements", {}).get("source_bound_signed_zone_speed", {})
        if measured.get("method") != "source_bound_zone_measurement":
            raise ValueError("Comparison lacks source-bound speed measurement")
        sources = measured.get("sources", {})
        for name in ("road.xodr", "installed-sign-review.json", "zone-establishment.json", "actor-poses.jsonl", "reference_corner.mkv"):
            if sources.get(name) != sha(stage / name):
                raise ValueError("Comparison source changed: " + name)
        observations.append((case_id, config, measured["value"], sha(stage / "analysis-report.json")))
    configs = [item[1] for item in observations]
    for field in ("law_id", "cell_id", "actor", "rate_hz", "duration_s", "cameras", "required_atoms", "source_packets"):
        if any(config[field] != configs[0][field] for config in configs[1:]):
            raise ValueError("Comparison fixed condition changed: " + field)
    if [c["speed_case"] for c in configs] != ["below", "at", "above"]:
        raise ValueError("Signed-zone speed request contrast changed")
    if [x[2]["authorized_mph"] for x in observations] != [25, 25, 25]:
        raise ValueError("Signed-zone authorized value changed")
    observed = [x[2] for x in observations]
    if not (observed[0]["frames_below_authorized_in_zone"] > 0 and
            observed[1]["frames_at_authorized_in_zone"] > 0 and
            observed[2]["frames_above_authorized_in_zone"] > 0):
        raise ValueError("Below/at/above source measurements differ from comparison")
    for name in ("road.xodr", "zone-establishment.json", "installed-sign-review.json", "reference_corner.mkv"):
        if len({sha(Path(read(paths[case])["analysis_directory"]) / name) for case in comparison["case_ids"]}) != 1:
            raise ValueError("Signed-zone fixed source changed: " + name)
    return {"format": "c179819-independent-comparison-audit-v1",
            "comparison_id": comparison_id, "case_ids": comparison["case_ids"],
            "fixed_conditions_checked": True, "differences_checked": True,
            "analysis_sha256": {case: digest for case, _, _, digest in observations},
            "physical_or_legal_acceptance_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--processing", action="append", required=True)
    parser.add_argument("--omit-case")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    value = audit(args.comparison, args.processing, args.omit_case)
    if args.output.exists():
        raise ValueError("Retain previous comparison audit result")
    args.output.write_text(json.dumps(value, indent=2) + "\n")
    print(json.dumps({"passed": True, "comparison_id": args.comparison}))


if __name__ == "__main__":
    main()
