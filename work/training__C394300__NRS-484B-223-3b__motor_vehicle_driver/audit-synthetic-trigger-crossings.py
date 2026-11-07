"""Measure isolated fallback crossings from exact saved synthetic package sources."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "native"))
from fallback_triggers import evaluate_native, evaluate_pixels

CASES = ("witness_1", "witness_2", "numeric_1_0", "numeric_1_1", "numeric_1_2")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_rows(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows))


def audit():
    manifest = json.loads((HERE / "draft-execution-manifest.json").read_text())
    records = []
    for case in CASES:
        lines = (HERE / f"package-compatibility-{case}.log").read_text().splitlines()
        if len(lines) != 2 or not lines[0].startswith("scratch "):
            raise ValueError("Exact primary package log absent")
        scratch = Path(lines[0][8:])
        package = json.loads(lines[1])
        entry = next(item for item in manifest["cases"] if item["case_id"].endswith("__" + case))
        source = scratch / "fixture/native_samples.jsonl"
        video = scratch / "fixture/approach.mkv"
        if (package["positive"]["construction_sha256"] != entry["construction_sha256"]
                or package["positive"]["passed"] is not True
                or not source.is_file() or not video.is_file()):
            raise ValueError("Saved source not bound to exact current package")
        rows = [json.loads(line) for line in source.read_text().splitlines()]
        if len(rows) != 480:
            raise ValueError("Saved 24-second source differs")
        baseline = evaluate_native(source, case)
        if (baseline["source_kind"] != "synthetic_diagnostic"
                or baseline["fallback1"]["triggered"]
                or baseline["fallback2"]["triggered"]):
            raise ValueError("Synthetic baseline is not neutral")
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            source_fault = temp / "fault.jsonl"
            lane_fault = copy.deepcopy(rows)
            for row in lane_fault:
                if row["time_s"] <= 6 and row["native_lane_id"] == -1:
                    row["native_lane_id"] = -2
            write_rows(source_fault, lane_fault)
            f1 = evaluate_native(source_fault, case)
            if not f1["fallback1"]["triggered"] or f1["fallback2"]["triggered"]:
                raise ValueError("Lane-entry fault is not isolated fallback1")
            route_fault = copy.deepcopy(rows)
            row = route_fault[-1]
            row["native_center_xy_m"][0] += 0.5
            for vertex in row["native_body_xy_m"]:
                vertex[0] += 0.5
            write_rows(source_fault, route_fault)
            f2 = evaluate_native(source_fault, case)
            if (f2["fallback1"]["triggered"] or not f2["fallback2"]["triggered"]
                    or f2["fallback2"]["max_route_error_m"] <= 0.35):
                raise ValueError("Route fault is not isolated fallback2")
            annotation = temp / "pixels.json"

            def pixels(visible):
                annotation.write_text(json.dumps({"source_kind": "synthetic_diagnostic",
                    "source_video_sha256": sha(video),
                    "approach_frames": [{"frame": i, "original_pixels_reviewed": False,
                        "body_visible": True, "center_lane_marking_visible": i < visible}
                        for i in range(20)]}))
                return evaluate_pixels(annotation, video)

            at_threshold = pixels(19)
            below_threshold = pixels(18)
            if (at_threshold["fallback3_triggered"]
                    or not below_threshold["fallback3_triggered"]
                    or below_threshold["source_kind"] != "synthetic_diagnostic"):
                raise ValueError("Synthetic pixel threshold differs")
            changed = temp / "changed.mkv"
            changed.write_bytes(video.read_bytes() + b"changed")
            try:
                evaluate_pixels(annotation, changed)
            except ValueError:
                pass
            else:
                raise ValueError("Changed source video accepted")
            mixed = copy.deepcopy(rows)
            mixed[0]["controller_request"].pop("synthetic_diagnostic")
            write_rows(source_fault, mixed)
            try:
                evaluate_native(source_fault, case)
            except ValueError:
                pass
            else:
                raise ValueError("Mixed synthetic/original rows accepted")
        records.append({"case": case, "saved_rows": 480,
            "native_samples_sha256": sha(source), "approach_video_sha256": sha(video),
            "baseline_route_error_m": baseline["fallback2"]["max_route_error_m"],
            "route_fault_error_m": f2["fallback2"]["max_route_error_m"],
            "isolated_fallbacks": [1, 2, 3],
            "changed_video_and_mixed_provenance_rejected": True})
    return {"passed": True, "records": records, "native_executed": False,
            "original_pixels_reviewed": False,
            "scope": "source-hashed 480-frame synthetic diagnostics; no original Native or pixel claim"}


if __name__ == "__main__":
    print(json.dumps(audit(), indent=2))
