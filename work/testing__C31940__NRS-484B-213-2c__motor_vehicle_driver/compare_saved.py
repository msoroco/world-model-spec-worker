"""Independent saved-only, source-bound bridge comparison audit."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

FACTORS = {
    "distance_beyond_at": "bridge_distance_front_m",
    "distance_at_within": "bridge_distance_front_m",
    "view_obstructed_clear": "ray_brackets",
    "left_side_right_side": "left_body_edge_m",
    "one_way_exception": "one_way_highway",
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def source_report(folder, case_id, diagnostic):
    folder = Path(folder).resolve()
    provenance = read(folder / "acquisition-provenance.json")
    if diagnostic:
        if provenance.get("diagnostic_fixture") is not True:
            raise ValueError("positive CPU comparison requires explicit diagnostic fixture")
    elif provenance.get("diagnostic_fixture") is True:
        raise ValueError("synthetic fixture cannot establish Native comparison")
    report = read(folder / "analysis-report.json")
    if report.get("case_id") != case_id or report.get("analysis_complete") is not True:
        raise ValueError("saved analysis case identity or completeness differs")
    for name, expected in report["measurements"]["measure_bridge_approach"]["sources"].items():
        if sha(folder / name) != expected:
            raise ValueError("saved original source changed: " + name)
    if not diagnostic:
        pixel = read(folder / "pixel-review.json")
        if pixel.get("case_id") != case_id or pixel.get("actual_pixels_visible") is not True:
            raise ValueError("independent actual pixel review missing")
        result = read(folder / "result.json")
        if result.get("physical_checks", {}).get("attempt", {}).get("status") != "met":
            raise ValueError("Native physical completion unconfirmed")
    return report["measurements"]["measure_bridge_approach"]["value"]


def audit(plan_path, left_path, right_path, comparison_id, diagnostic=False):
    plan = read(plan_path)
    comparison = next((row for row in plan["comparisons"] if row["comparison_id"] == comparison_id), None)
    if comparison is None or comparison_id not in FACTORS:
        raise ValueError("unknown exact bridge comparison")
    left, right = (source_report(path, case, diagnostic) for path, case in
                   zip((left_path, right_path), comparison["case_ids"]))
    source_names = ("map.source", "centerline.source", "bridge.source")
    for name in source_names:
        if comparison_id != "one_way_exception" and sha(Path(left_path) / "reviewed-sources" / name) != sha(Path(right_path) / "reviewed-sources" / name):
            raise ValueError("reviewed fixed source differs: " + name)
    lc, rc = (read(Path(path) / "config.json") for path in (left_path, right_path))
    for key in ("law_id", "cell_id", "actor", "rate_hz", "duration_s", "cameras"):
        if lc.get(key) != rc.get(key):
            raise ValueError("shared construction contract differs: " + key)
    if left["bridge_entrance_station_m"] != right["bridge_entrance_station_m"]:
        raise ValueError("bridge entrance reference differs")
    if comparison_id != "one_way_exception" and left["one_way_highway"] != right["one_way_highway"]:
        raise ValueError("uncontrolled one-way status differs")
    a, b = left["per_frame"], right["per_frame"]
    if not a or not b or len(a) != len(b):
        raise ValueError("original comparison frame history differs")
    factor = FACTORS[comparison_id]
    if factor == "one_way_highway":
        changed = left[factor] != right[factor]
    else:
        changed = any(x[factor] != y[factor] for x, y in zip(a, b))
    if not changed:
        raise ValueError("declared bridge factor has no measured difference")
    for x, y in zip(a, b):
        if x["original_frame"] != y["original_frame"]:
            raise ValueError("original frame alignment differs")
        for field in ("bridge_distance_front_m", "left_body_edge_m", "ray_brackets"):
            if field == factor or (comparison_id == "one_way_exception" and field == "ray_brackets"):
                continue
            if x[field] != y[field]:
                raise ValueError("uncontrolled measured condition differs: " + field)
    return {"format": "worker-source-bound-comparison-audit-diagnostic" if diagnostic else "worker-source-bound-comparison-audit",
            "comparison_id": comparison_id, "case_ids": comparison["case_ids"],
            "factor_measurement": factor, "left_report_sha256": sha(Path(left_path) / "analysis-report.json"),
            "right_report_sha256": sha(Path(right_path) / "analysis-report.json"),
            "legal_judgment": "unresolved", "physical_acceptance_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--left-attempt", type=Path, required=True)
    parser.add_argument("--right-attempt", type=Path, required=True)
    parser.add_argument("--comparison", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostic-protocol", action="store_true")
    args = parser.parse_args()
    result = audit(args.plan, args.left_attempt, args.right_attempt, args.comparison, args.diagnostic_protocol)
    if args.output.exists():
        raise ValueError("retain prior comparison audit output")
    args.output.write_text(json.dumps(result, indent=2) + "\n")
    print(result["comparison_id"])


if __name__ == "__main__":
    main()
