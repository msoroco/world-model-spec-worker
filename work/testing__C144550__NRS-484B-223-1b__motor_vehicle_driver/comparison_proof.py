"""Source-bound CPU comparisons for five synthetic lane-change exact cases.

This checks diagnostic constructions only. Gap values describe body geometry;
they are not a legal safe-gap threshold or a driver's actual judgment.
"""

import copy
import hashlib
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
from lane_change_measurements import measure_exact_case
from late_lane_change_measurements import measure_exact_case as measure_late_case


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NAMES = (
    "left_signal_before_clear_gap",
    "left_signal_late_clear_gap",
    "left_wrong_signal_clear_gap",
    "left_signal_before_close_gap",
    "right_signal_before_clear_gap",
)


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sources():
    index = read(HERE / "diagnostic-source-audits.json")
    require(index["assignment_id"] == HERE.name, "Source audit assignment changed")
    require(digest(HERE / index["script"]) == index["script_sha256"], "Source auditor changed")
    require(digest(HERE / "execution-manifest.json") == index["execution_manifest_sha256"], "Execution manifest changed")
    cases = {}
    for entry in index["cases"]:
        name = entry["case_id"].split("__")[-1]
        require(name in NAMES and name not in cases, "Source audit case inventory changed")
        attempt = ROOT / entry["attempt"]
        receipt = read(attempt / "compatibility.json")
        require(receipt.get("passed") is True and receipt.get("candidate_id") == "primary", "Current primary compatibility failed")
        require(digest(HERE / entry["positive_log"]) == entry["positive_sha256"], "Source audit log changed")
        inventory = receipt["fixture_manifest"]
        for filename in ("lane_context.json", "lane_history.jsonl", "video_frames.jsonl", "trace.jsonl", "capture/evidence.jsonl"):
            require(digest(attempt / filename) == inventory[filename], "Original source changed: " + filename)
        measure = measure_late_case if name == "left_signal_late_clear_gap" else measure_exact_case
        measured = measure(attempt, entry["case_id"])
        require(measured["observed_signal_pattern_matches_plan"], "Observed signal pattern differs")
        cases[name] = {
            "case_id": entry["case_id"], "attempt": entry["attempt"],
            "context": read(attempt / "lane_context.json"),
            "history": rows(attempt / "lane_history.jsonl"),
            "frames": rows(attempt / "video_frames.jsonl"),
            "trace": rows(attempt / "trace.jsonl"),
            "capture": rows(attempt / "capture/evidence.jsonl"),
            "measured": measured,
            "source_hashes": {key: inventory[key] for key in ("lane_context.json", "lane_history.jsonl", "video_frames.jsonl", "trace.jsonl", "capture/evidence.jsonl")},
        }
        require(all(len(cases[name][key]) == 900 for key in ("history", "frames", "trace", "capture")), "Comparison frame count differs")
    require(set(cases) == set(NAMES), "Source audit does not cover all selected cases")
    return cases


def without(row, *keys):
    return {key: value for key, value in row.items() if key not in keys}


def capture_without_lamps(row):
    value = copy.deepcopy(row)
    for person in value["original_observations"]["participants"]:
        person.get("light_attributes", {}).pop("light_LeftBlinker", None)
        person.get("light_attributes", {}).pop("light_RightBlinker", None)
    return value


def capture_without_target_position(row):
    value = copy.deepcopy(row)
    target = value["original_observations"]["participants"][1]
    target.pop("position_m", None)
    target.pop("body_vertices_m", None)
    return value


def check_capture_mirror(a, b):
    left, right = copy.deepcopy(a), copy.deepcopy(b)
    for value in (left, right):
        value["world"]["road_projection"].pop("lane_id", None)
        for person in value["original_observations"]["participants"]:
            person.get("light_attributes", {}).pop("light_LeftBlinker", None)
            person.get("light_attributes", {}).pop("light_RightBlinker", None)
    for parent in ("ego",):
        require(left[parent]["position_m"][0] == right[parent]["position_m"][0]
                and abs(0.5 - left[parent]["position_m"][1] - right[parent]["position_m"][1]) < 1e-8,
                "Capture ego lateral mirror differs")
        right[parent]["position_m"][1] = left[parent]["position_m"][1]
        for av, bv in zip(left[parent]["body_vertices_m"], right[parent]["body_vertices_m"]):
            require(av[0] == bv[0] and abs(0.5 - av[1] - bv[1]) < 1e-8, "Capture ego body mirror differs")
            bv[1] = av[1]
    for aa, bb in zip(left["original_observations"]["participants"], right["original_observations"]["participants"]):
        require(aa["position_m"][0] == bb["position_m"][0]
                and abs(0.5 - aa["position_m"][1] - bb["position_m"][1]) < 1e-8,
                "Capture participant lateral mirror differs")
        bb["position_m"][1] = aa["position_m"][1]
        for av, bv in zip(aa["body_vertices_m"], bb["body_vertices_m"]):
            require(av[0] == bv[0] and abs(0.5 - av[1] - bv[1]) < 1e-8, "Capture participant body mirror differs")
            bv[1] = av[1]
    require(left == right, "Capture direction comparison changed fixed conditions")


def signal_order(clear, late, wrong):
    for candidate, expected in ((late, "off"), (wrong, "right")):
        require(candidate["context"] == clear["context"], "Signal comparison lane context differs")
        require(candidate["frames"] == clear["frames"], "Signal comparison frame map differs")
        for a, b, ta, tb, ca, cb in zip(clear["history"], candidate["history"], clear["trace"], candidate["trace"], clear["capture"], candidate["capture"]):
            require(without(a, "indicator") == without(b, "indicator"), "Signal comparison changed non-signal body history")
            require(without(ta, "ego_lamp_bits") == without(tb, "ego_lamp_bits"), "Signal comparison changed non-lamp trace")
            require(capture_without_lamps(ca) == capture_without_lamps(cb), "Signal comparison changed non-lamp capture")
        require(candidate["measured"]["observed"]["indicator_at_movement"] == expected, "Signal contrast at movement differs")
        require(candidate["measured"]["observed"]["appropriate_signal_before_movement"] is False, "Signal contrast timing differs")
    require(clear["measured"]["observed"]["appropriate_signal_before_movement"] is True, "Baseline signal timing differs")
    late_movement = late["measured"]["first_body_leaves_lane"]
    late_signal = late["measured"]["first_appropriate_signal"]
    require(late_signal is not None and late_signal["frame"] > late_movement["frame"], "Late signal did not follow body departure")
    require(late_signal["frame"] == late_movement["frame"] + 1, "Late signal frame offset differs")
    return {"frames": 900, "baseline_indicator_at_movement": "left", "late_indicator_at_movement": "off", "late_signal_frame": late_signal["frame"], "late_body_departure_frame": late_movement["frame"], "wrong_indicator_at_movement": "right"}


def target_lane_gap(clear, close):
    require(clear["context"] == close["context"], "Gap comparison lane context differs")
    require(clear["frames"] == close["frames"] and clear["trace"] == close["trace"], "Gap comparison route or frame map differs")
    for a, b, ca, cb in zip(clear["history"], close["history"], clear["capture"], close["capture"]):
        require(without(a, "target_lane_bodies") == without(b, "target_lane_bodies"), "Gap comparison changed ego history")
        require(capture_without_target_position(ca) == capture_without_target_position(cb), "Gap comparison changed non-target capture")
        require(len(a["target_lane_bodies"]) == len(b["target_lane_bodies"]) == 1, "Target body inventory differs")
        aa, bb = a["target_lane_bodies"][0], b["target_lane_bodies"][0]
        require(without(aa, "body_vertices_xy_m") == without(bb, "body_vertices_xy_m"), "Target identity differs")
        for av, bv in zip(aa["body_vertices_xy_m"], bb["body_vertices_xy_m"]):
            require(abs(av[0] - bv[0] - 5.0) < 1e-8 and av[1] == bv[1], "Target body shift differs")
        ac = ca["original_observations"]["participants"][1]
        bc = cb["original_observations"]["participants"][1]
        require(abs(ac["position_m"][0] - bc["position_m"][0] - 5.0) < 1e-8,
                "Capture target position shift differs")
        for av, bv in zip(ac["body_vertices_m"], bc["body_vertices_m"]):
            require(abs(av[0] - bv[0] - 5.0) < 1e-8 and av[1:] == bv[1:], "Capture target body shift differs")
    a = clear["measured"]["observed"]["nearest_target_body_longitudinal_gap_at_movement_m"]
    b = close["measured"]["observed"]["nearest_target_body_longitudinal_gap_at_movement_m"]
    require(abs(a - 8.0) < 1e-8 and abs(b - 3.0) < 1e-8, "Measured gap contrast differs")
    return {"frames": 900, "clear_gap_m": a, "close_gap_m": b, "target_body_shift_m": 5.0}


def lane_change_direction(left, right):
    lc, rc = left["context"], right["context"]
    require(lc["change_direction"] == "left" and rc["change_direction"] == "right", "Direction contrast differs")
    require(lc["source_lane_id"] == rc["target_lane_id"] and lc["target_lane_id"] == rc["source_lane_id"], "Lane identity exchange differs")
    require(without(lc, "change_direction", "source_lane_id", "target_lane_id", "source_lane_polygon_xy_m") == without(rc, "change_direction", "source_lane_id", "target_lane_id", "source_lane_polygon_xy_m"), "Direction comparison road context differs")
    require(left["frames"] == right["frames"], "Direction comparison frame map differs")
    for a, b, ca, cb in zip(left["history"], right["history"], left["capture"], right["capture"]):
        check_capture_mirror(ca, cb)
        require(a["frame"] == b["frame"] and a["time_s"] == b["time_s"], "Direction frame timing differs")
        lane_exchange = {lc["source_lane_id"]: rc["source_lane_id"], lc["target_lane_id"]: rc["target_lane_id"]}
        require(a["road_id"] == b["road_id"] and b["ego_lane_id"] == lane_exchange.get(a["ego_lane_id"]), "Direction road/lane differs")
        require(b["indicator"] == {"left": "right", "right": "left", "off": "off"}[a["indicator"]], "Direction lamp mirror differs")
        for av, bv in zip(a["ego_body_vertices_xy_m"], b["ego_body_vertices_xy_m"]):
            require(av[0] == bv[0] and abs(0.5 - av[1] - bv[1]) < 1e-8, "Ego lateral mirror differs")
        for aa, bb in zip(a["target_lane_bodies"], b["target_lane_bodies"]):
            require(aa["lane_id"] == lc["target_lane_id"] and bb["lane_id"] == rc["target_lane_id"], "Target lane mirror differs")
            for av, bv in zip(aa["body_vertices_xy_m"], bb["body_vertices_xy_m"]):
                require(av[0] == bv[0] and abs(0.5 - av[1] - bv[1]) < 1e-8, "Target lateral mirror differs")
    a = left["measured"]["observed"]["nearest_target_body_longitudinal_gap_at_movement_m"]
    b = right["measured"]["observed"]["nearest_target_body_longitudinal_gap_at_movement_m"]
    require(abs(a - 8.0) < 1e-8 and abs(b - a) < 1e-8, "Direction gap differs")
    require(right["measured"]["observed"]["appropriate_signal_before_movement"] is True, "Right signal timing differs")
    return {"frames": 900, "left_gap_m": a, "right_gap_m": b, "lateral_reflection_axis_y_m": 0.25}


def prove():
    cases = sources()
    clear, late, wrong, close, right = (cases[name] for name in NAMES)
    comparisons = {
        "signal_order": signal_order(clear, late, wrong),
        "target_lane_gap": target_lane_gap(clear, close),
        "lane_change_direction": lane_change_direction(clear, right),
    }
    negatives = {}
    for name, function, args, mutation in (
        ("signal_order", signal_order, (clear, late, wrong), lambda x: x["capture"][0]["ego"]["position_m"].__setitem__(0, -99)),
        ("target_lane_gap", target_lane_gap, (clear, close), lambda x: x["history"][0]["target_lane_bodies"][0]["body_vertices_xy_m"][0].__setitem__(0, -99)),
        ("lane_change_direction", lane_change_direction, (clear, right), lambda x: x["history"][0]["ego_body_vertices_xy_m"][0].__setitem__(1, -99)),
    ):
        changed = copy.deepcopy(args[1]); mutation(changed)
        try:
            function(args[0], changed, *args[2:])
        except ValueError as error:
            negatives[name] = str(error)
        else:
            raise ValueError("Changed comparison source was accepted: " + name)
    return {
        "format": "worker-lane-change-source-comparison-proof",
        "assignment_id": HERE.name,
        "comparison_script_sha256": digest(Path(__file__)),
        "source_audit_index_sha256": digest(HERE / "diagnostic-source-audits.json"),
        "case_source_hashes": {name: value["source_hashes"] for name, value in cases.items()},
        "late_case_pattern_matches_measurement_contract": late["measured"]["observed_signal_pattern_matches_plan"],
        "comparisons": comparisons,
        "changed_source_rejections": negatives,
        "diagnostic_only": True,
        "native_source_accepted": False,
        "driver_ascertained_safety_judgment": "unresolved",
        "legal_conclusion": "unresolved",
    }


if __name__ == "__main__":
    output = HERE / "comparison-proof.json"
    output.write_text(json.dumps(prove(), sort_keys=True, indent=2) + "\n")
    print(output)
