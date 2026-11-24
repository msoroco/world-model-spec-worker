"""Independently check the two reverse endpoint cases on one authored junction."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
MODULE = HERE / "audit-selected-delivery.py"
SPEC = importlib.util.spec_from_file_location("selected_delivery_audit", MODULE)
DELIVERY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(DELIVERY)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def audit(attempt_a, saved_a, attempt_b, saved_b, reject_road_drift=False):
    manifest = read(HERE / "execution-manifest.json")
    a, b = manifest["cases"]
    first = DELIVERY.audit(a["case_id"], attempt_a, saved_a)
    second = DELIVERY.audit(b["case_id"], attempt_b, saved_b)
    road_a = sha(attempt_a / "road.xodr")
    road_b = sha(attempt_b / "road.xodr")
    if reject_road_drift or road_a != road_b:
        raise ValueError("Comparison fixed road source changed")
    config_a, config_b = read(attempt_a / "config.json"), read(attempt_b / "config.json")
    for key in ("cell_id", "law_id", "actor", "duration_s", "rate_hz", "required_atoms",
                "source_packets", "mandatory_channels", "recording_description", "cameras",
                "engineering_knobs"):
        if config_a[key] != config_b[key]:
            raise ValueError("Comparison fixed configuration changed: " + key)
    source_a, source_b = rows(attempt_a / "native_samples.jsonl"), rows(attempt_b / "native_samples.jsonl")
    if len(source_a) != 600 or len(source_b) != 600:
        raise ValueError("Comparison lacks complete source rows")
    for left, right in zip(source_a, source_b):
        for key in ("video_frame", "native_frame", "time_s", "native_forward_xy",
                    "heading_deg", "native_intersection_survey", "intersection_polygon_xy_m"):
            if left[key] != right[key]:
                raise ValueError("Controlled source changed outside reverse endpoint: " + key)
    report_a = read(attempt_a / "analysis-report.json")
    report_b = read(attempt_b / "analysis-report.json")
    metric_a = report_a["measurements"]["backing_intersection_relation"]["value"]
    metric_b = report_b["measurements"]["backing_intersection_relation"]["value"]
    if (metric_a["max_backing_intersection_overlap_m2"] != 0
            or metric_b["max_backing_intersection_overlap_m2"] <= 3
            or metric_a["backing_frames"] != metric_b["backing_frames"]):
        raise ValueError("Controlled full-body reverse contrast absent")
    return {"format": "c110763-selected-comparison-cpu-audit-v1", "passed": True,
            "case_ids": [a["case_id"], b["case_id"]],
            "fixed_road_sha256": road_a, "joined_source_rows": 600,
            "delivery_receipt_sha256": [hashlib.sha256(json.dumps(item, sort_keys=True).encode()).hexdigest()
                                        for item in (first, second)],
            "max_reverse_overlap_m2": [metric_a["max_backing_intersection_overlap_m2"],
                                       metric_b["max_backing_intersection_overlap_m2"]],
            "physical_success_claimed": False, "legal_verdict_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for name in ("attempt-a", "saved-a", "attempt-b", "saved-b"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--reject-road-drift", action="store_true")
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt_a, args.saved_a, args.attempt_b, args.saved_b,
                           args.reject_road_drift)))
