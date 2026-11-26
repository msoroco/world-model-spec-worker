"""Independent three-case source and fixed-condition speed comparison."""
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


def audit(comparison_id, specifications, omit_case):
    plan = read(HERE / "case-plan.json")
    comparison = next((c for c in plan["comparisons"] if c["comparison_id"] == comparison_id), None)
    if comparison is None:
        raise ValueError("Unknown comparison")
    paths = dict(item.split("=", 1) for item in specifications)
    if set(paths) != set(comparison["case_ids"]) or omit_case:
        raise ValueError("Missing comparison case: " + str(omit_case or sorted(set(comparison["case_ids"]) - set(paths))))
    manifest = read(HERE / "execution-manifest.json")
    observations = []
    for case in comparison["case_ids"]:
        entry = next(e for e in manifest["cases"] if e["case_id"] == case)
        saved = read(paths[case])
        if (saved.get("case_id") != case or saved.get("candidate_id") != "primary" or
                saved.get("passed") is not True or saved.get("recorded_only") is not True or
                saved.get("native_revision", {}).get("construction_sha256") != entry["construction_sha256"] or
                saved.get("timestamp_joins", {}).get("frames") != 600):
            raise ValueError("Selected comparison source differs")
        stage = Path(saved["analysis_directory"])
        config = read(stage / "config.json")
        report = read(stage / "analysis-report.json")
        speed = report.get("measurements", {}).get("blind_intersection_speed_mph", {})
        context = report.get("measurements", {}).get("sight_and_exception_context", {})
        if (speed.get("method") != "measure_blind_speed" or
                speed.get("sources", {}).get("native-ego-readback.jsonl") != sha(stage / "native-ego-readback.jsonl") or
                speed.get("sources", {}).get("review.json") != sha(stage / "review.json") or
                context.get("sources", {}).get("native-context-readback.json") != sha(stage / "native-context-readback.json")):
            raise ValueError("Comparison lacks source-bound speed or sight")
        observations.append((case, config, float(speed["value"]), context["value"], sha(stage / "analysis-report.json")))
    base = observations[0][1]
    for _, config, _, _, _ in observations[1:]:
        for field in ("law_id", "cell_id", "actor", "rate_hz", "duration_s", "cameras",
                      "required_atoms", "source_packets"):
            if config[field] != base[field]:
                raise ValueError("Fixed comparison condition changed: " + field)
    speeds = [item[2] for item in observations]
    if not (speeds[0] < speeds[1] < speeds[2] and speeds[0] < 15 < speeds[2] and abs(speeds[1] - 15) <= 0.1):
        raise ValueError("Below/at/above observed speed contrast unproven")
    sight = [item[3] for item in observations]
    if any(value["sight_limited_frame_count"] <= 0 or value["last_100ft_sampled_frames"] <= 0
           or set(value["exception_source_refs"]) != {"through_street", "traffic_controlled_intersection"}
           for value in sight):
        raise ValueError("Sight-limited scope or separate exception source absent")
    return {"format": "c24758-independent-comparison-audit-v1", "comparison_id": comparison_id,
            "case_ids": comparison["case_ids"], "fixed_conditions_checked": True,
            "deliberate_speed_difference_checked": True,
            "observed_speed_mph": dict(zip(comparison["case_ids"], speeds)),
            "analysis_sha256": {case: digest for case, _, _, _, digest in observations},
            "physical_or_legal_acceptance_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--processing", action="append", required=True)
    parser.add_argument("--omit-case")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    receipt = audit(args.comparison, args.processing, args.omit_case)
    if args.output.exists():
        raise ValueError("Retain previous comparison audit result")
    args.output.write_text(json.dumps(receipt, indent=2) + "\n")
    print(json.dumps({"passed": True, "comparison_id": args.comparison}))


if __name__ == "__main__":
    main()
