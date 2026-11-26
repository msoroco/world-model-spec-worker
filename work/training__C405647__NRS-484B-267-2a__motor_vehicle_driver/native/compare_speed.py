"""Independent source comparison for the two moving-emergency-vehicle cases."""
import argparse
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("observed_speed", HERE / "observed_speed.py")
meter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(meter)


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def compare(path_a, path_b, *, synthetic=False):
    a = meter.measure(path_a, synthetic=synthetic)
    b = meter.measure(path_b, synthetic=synthetic)
    if (a["case_id"], b["case_id"]) != (meter.BASE + "a", meter.BASE + "b"):
        raise ValueError("Selected comparison cases differ")
    rows_a, rows_b = _rows(path_a), _rows(path_b)
    fixed_fields = ("officer_direction", "officer_direction_source_id",
                    "road_context_source_id", "weather_context_source_id",
                    "posted_limit_mps", "visibility_m", "wet_road")
    for index, (left, right) in enumerate(zip(rows_a, rows_b)):
        if any(left.get(key) != right.get(key) for key in fixed_fields):
            raise ValueError("Fixed road, weather or officer context differs at frame " + str(index))
        if left["qualifying_vehicle"] != right["qualifying_vehicle"]:
            raise ValueError("Fixed qualifying vehicle differs at frame " + str(index))
        if (left["time_s"], left["video_frame"], left["camera_frames"]) != (
                right["time_s"], right["video_frame"], right["camera_frames"]):
            raise ValueError("Fixed capture timeline differs at frame " + str(index))
        if index < 120 and abs(left["ego"]["speed_mps"] - right["ego"]["speed_mps"]) > 0.01:
            raise ValueError("Initial ego speed differs before intervention")
    if a["reduction_mps"] <= b["reduction_mps"] + 3:
        raise ValueError("Controlled speed difference missing")
    return {"format": "c405647-speed-comparison-v1",
            "comparison_id": meter.ASSIGNMENT_ID + "__selected_d6045110__comparison",
            "case_ids": [a["case_id"], b["case_id"]],
            "source_sha256": [a["source_sha256"], b["source_sha256"]],
            "fixed_context_checked_frames": meter.FRAMES,
            "reduction_difference_mps": round(a["reduction_mps"] - b["reduction_mps"], 5),
            "fixture_only": synthetic, "physical_completion_claimed": False,
            "legal_outcome_claimed": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition-a", required=True)
    parser.add_argument("--condition-b", required=True)
    parser.add_argument("--synthetic", action="store_true")
    args = parser.parse_args()
    print(json.dumps(compare(args.condition_a, args.condition_b, synthetic=args.synthetic),
                     indent=2, sort_keys=True))
