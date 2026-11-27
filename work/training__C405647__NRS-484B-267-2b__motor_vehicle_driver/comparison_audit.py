"""Independent source-bound comparisons for the five emergency caution probes."""
import argparse
import hashlib
import json
from pathlib import Path

AID = "training__C405647__NRS-484B-267-2b__motor_vehicle_driver"
PAIRS = {"caution_response": (1, 2), "qualifying_role": (1, 3),
         "moving_or_preparing": (1, 4), "officer_direction": (1, 5)}
CONTEXT = ("vehicle_authorization", "flashing_equipment", "flashing_qualification",
           "lamp_pixels", "lane_topology", "roadway_conditions", "traffic_conditions",
           "weather_conditions", "officer_direction", "hand_signal_pixels")

def require(ok, message):
    if not ok:
        raise ValueError(message)

def read(path):
    return json.loads(Path(path).read_text())

def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def audit(comparison, left, right, output):
    key = comparison.removeprefix(AID + "__")
    require(comparison == AID + "__" + key and key in PAIRS, "Unknown exact comparison")
    roots = (Path(left), Path(right))
    expected = [AID + f"__probe_0{i}" for i in PAIRS[key]]
    configs = [read(root / "config.json") for root in roots]
    require([c["case_id"] for c in configs] == expected, "Comparison case order differs")
    for field in ("law_id", "cell_id", "actor", "frozen_cell", "rate_hz",
                  "duration_s", "frames", "cameras"):
        require(configs[0][field] == configs[1][field], "Fixed policy differs: " + field)
    for name in ("road.xodr", *("source_context/" + c + ".txt" for c in CONTEXT)):
        require(sha(roots[0] / name) == sha(roots[1] / name),
                "Fixed road or source differs: " + name)
    traces = [rows(root / "emergency-native.jsonl") for root in roots]
    maps = [rows(root / "video_frames.jsonl") for root in roots]
    lamps = [read(root / "lamp-pixel-review.json")["frames"] for root in roots]
    signals = [read(root / "signal-pixel-review.json")["frames"] for root in roots]
    require(all(len(part) == 600 for part in traces + maps + lamps + signals),
            "Comparison lacks 600 original source frames")
    for root in roots:
        review = read(root / "emergency-review.json")
        for name, ref in review["sources"].items():
            require(sha(root / ref["path"]) == ref["sha256"],
                    "Source hash differs: " + name)
    for i in range(600):
        a, b = traces[0][i], traces[1][i]
        require(a["frame"] == b["frame"] == i and
                a["t_s"] == b["t_s"] == maps[0][i]["time_s"] == maps[1][i]["time_s"] and
                a["native_frame"] == maps[0][i]["native_frame"] and
                b["native_frame"] == maps[1][i]["native_frame"] and
                lamps[0][i] == lamps[1][i] and
                a["emergency_light_state"] == b["emergency_light_state"] and
                a["traffic"] == b["traffic"] is None and
                a["weather_precipitation"] == b["weather_precipitation"] == 0 and
                a["weather_wetness"] == b["weather_wetness"] == 0,
                "Frame, lamp, traffic or weather fixed conditions differ")
        if key == "caution_response":
            require(a["emergency"] == b["emergency"] and
                    a["ego"]["speed_mps"] < b["ego"]["speed_mps"] and
                    a["ego"]["y_m"] != b["ego"]["y_m"] and
                    signals[0][i] == signals[1][i],
                    "Caution response contrast differs")
        elif key == "qualifying_role":
            require(a["ego"] == b["ego"] and a["emergency"] == b["emergency"] and
                    signals[0][i] == signals[1][i],
                    "Qualifying role changed motion or signals")
        elif key == "moving_or_preparing":
            require(a["ego"] == b["ego"] and a["emergency"]["speed_mps"] > 0 and
                    b["emergency"]["speed_mps"] == 0 and
                    not signals[0][i]["hand_signal_visible"] and
                    signals[1][i]["hand_signal_visible"] == (30 <= i < 500),
                    "Moving versus visible preparation contrast differs")
        else:
            require(a["ego"] == b["ego"] and a["emergency"] == b["emergency"] and
                    not signals[0][i]["officer_direction_visible"] and
                    signals[1][i]["officer_direction_visible"] == (30 <= i < 500),
                    "Officer direction contrast differs")
    reviews = [read(root / "emergency-review.json") for root in roots]
    if key == "qualifying_role":
        require([r["qualification_role"] for r in reviews] ==
                ["authorized_emergency", "official_regulatory"],
                "Role distinction absent from reviewed sources")
    else:
        require(reviews[0]["qualification_role"] == reviews[1]["qualification_role"],
                "Fixed qualification role differs")
    report = {"format": "worker-comparison-audit", "comparison_id": comparison,
              "case_ids": expected, "passed": True, "frames": 600,
              "fixed_conditions_checked": True, "declared_difference_checked": True,
              "source_sha256": [{name: sha(root / name) for name in
                                  ("config.json", "road.xodr", "emergency-review.json",
                                   "emergency-native.jsonl", "video_frames.jsonl")}
                                 for root in roots],
              "physical_or_legal_acceptance": False}
    Path(output).write_text(json.dumps(report, indent=2) + "\n")
    return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    for field in ("comparison", "left", "right", "output"):
        parser.add_argument("--" + field, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.comparison, args.left, args.right, args.output)))
