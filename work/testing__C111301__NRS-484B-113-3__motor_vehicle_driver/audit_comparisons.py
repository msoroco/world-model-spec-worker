"""Independent source-bound response contrasts for diagnostic attempts."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit(kind, root, negative=False):
    if kind not in ("pedestrian", "traffic"):
        raise ValueError("unknown comparison participant")
    source = __import__("saved_backing" if kind == "pedestrian" else "traffic_saved")
    measured = __import__("backing_measurements" if kind == "pedestrian" else "traffic_measurements")
    base = Path(root)
    yield_attempt = base / ("saved-" + kind + "_yield-attempt")
    continue_attempt = yield_attempt if negative else base / ("saved-" + kind + "_continue-attempt")
    if yield_attempt.resolve() == continue_attempt.resolve():
        raise ValueError("comparison requires distinct source attempts")
    left_case = HERE.name + "__" + kind + "_yield"
    right_case = HERE.name + "__" + kind + "_continue"
    left = source.process(yield_attempt, left_case, allow_diagnostic=True)
    right = source.process(continue_attempt, right_case, allow_diagnostic=True)
    if left["map_sha256"] != right["map_sha256"]:
        raise ValueError("fixed original map source changed")
    if [r["time_s"] for r in left["measurement"]["frames"]] != [r["time_s"] for r in right["measurement"]["frames"]]:
        raise ValueError("fixed original time window changed")
    contrast = measured.compare(left["measurement"], right["measurement"])
    audit_paths = [base / ("delivery-" + kind + "_" + suffix + "-positive.json") for suffix in ("yield", "continue")]
    for path in audit_paths:
        report = json.loads(path.read_text())
        if report.get("provenance_kind") != "synthetic_fixture" or not report["pixels"]["actual_pixels_decoded"]:
            raise ValueError("independent full pixel audit missing")
    return {"format": "c111301-independent-diagnostic-comparison", "comparison_id": kind + "_yield_response",
            "case_ids": [left_case, right_case], "source_ids": contrast["sources"],
            "fixed_map_sha256": left["map_sha256"], "fixed_observables": contrast["fixed_observables"] + ["time_s", "map_sha256"],
            "changed_observables": contrast["changed_observables"],
            "independent_delivery_audit_sha256": [sha(path) for path in audit_paths],
            "diagnostic_fixture": True, "physical_completion": False, "legal_judgment": "unresolved"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--kind", choices=("pedestrian", "traffic"), required=True)
    parser.add_argument("--root", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    result = audit(args.kind, args.root, args.negative)
    Path(args.output).write_text(json.dumps(result, indent=2) + "\n")
    print("independent diagnostic comparison passed")
