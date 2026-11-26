"""Recorded-only measurements for an exact preparing-to-move source attempt."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from preparing_runner import BASE, BRANCHES

FRAMES = 600
RATE = 20
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
ORIGINALS = ("preparing_observations.jsonl", "video_frames.jsonl", "trace.jsonl",
             "capture/manifest.json", "acquisition-provenance.json",
             *(view + ".mkv" for view in VIEWS))


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def measure(observations, mapping, case):
    branch = case.removeprefix(BASE)
    require(branch in BRANCHES and case == BASE + branch, "Exact preparing case differs")
    require(len(observations) == len(mapping) == FRAMES,
            "Recorded preparing duration differs")
    visible = []
    reach = None
    speeds = []
    for index, (state, frame) in enumerate(zip(observations, mapping)):
        require(state.get("case_id") == case
                and state.get("video_frame") == frame.get("video_frame") == index
                and state.get("native_frame") == frame.get("native_frame")
                and abs(state.get("time_s", -1) - index / RATE) < 1e-6
                and abs(frame.get("time_s", -1) - index / RATE) < 1e-6,
                "Recorded preparing frame join differs")
        ego = state.get("ego", {})
        vehicle = state.get("qualifying_vehicle", {})
        require(ego.get("actor_id") and vehicle.get("actor_id")
                and ego["actor_id"] != vehicle["actor_id"],
                "Recorded preparing participant missing")
        values = (ego.get("speed_mps"), ego.get("road_x_m"),
                  vehicle.get("speed_mps"), vehicle.get("road_x_m"))
        require(all(type(value) in (int, float) and math.isfinite(value)
                    for value in values), "Recorded preparing motion missing")
        if state.get(branch):
            visible.append(index)
        if reach is None and ego["road_x_m"] >= vehicle["road_x_m"]:
            reach = index
        speeds.append(ego["speed_mps"])
    require(visible and reach is not None and 0 < visible[0] < reach < FRAMES - 20,
            "Recorded visible indication or approach/pass missing")
    return {"first_visible_frame": visible[0], "first_reach_frame": reach,
            "initial_approach_speed_mps": sum(speeds[:40]) / 40,
            "last_approach_speed_mps": sum(speeds[reach - 20:reach]) / 20,
            "passing_speed_mps": sum(speeds[reach:reach + 20]) / 20,
            "reasonable_and_proper_legally_determined": False}


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    require(not output.exists() and not (attempt / "result.json").exists(),
            "Retain prior finalization; use a fresh attempt")
    for name in (*ORIGINALS, "config.json", "construction.json"):
        require((attempt / name).is_file(), "Missing required original source: " + name)
    config = json.loads((attempt / "config.json").read_text())
    construction = json.loads((attempt / "construction.json").read_text())
    require(config.get("case_id") == construction.get("case_id"),
            "Recorded preparing construction identity differs")
    provenance = json.loads((attempt / "acquisition-provenance.json").read_text())
    synthetic = provenance.get("diagnostic_fixture") is True
    if not synthetic:
        require(provenance.get("provenance_kind") == "native"
                and (attempt / "capture-seal.json").is_file(),
                "Original Native capture seal missing")
    hashes = {name: digest(attempt / name) for name in ORIGINALS}
    observations = [json.loads(line) for line in
                    (attempt / "preparing_observations.jsonl").read_text().splitlines()]
    mapping = [json.loads(line) for line in
               (attempt / "video_frames.jsonl").read_text().splitlines()]
    value = measure(observations, mapping, config["case_id"])
    report = {"format": "c405647-preparing-saved-analysis-v1",
              "case_id": config["case_id"], "measurements": {
                  "preparing_approach": {"method": "measure",
                                          "value": value, "sources": hashes}},
              "fixture_only": synthetic, "physical_acceptance_claimed": False,
              "legal_verdict_claimed": False}
    result = {"case_id": config["case_id"], "measured_values": value,
              "target_checks": [{"target": "visible preparing indication before approach and pass",
                                 "requested": True, "measured": value["first_visible_frame"] < value["first_reach_frame"],
                                 "method": "original 600-frame actor and camera time join",
                                 "tolerance": 0, "matched": True,
                                 "physical_cause_confirmed": False,
                                 "cause_evidence": ["preparing_observations.jsonl",
                                                    "video_frames.jsonl"]}],
              "setup_confirmed": False, "behavior_attempted": False,
              "maneuver_completed": False, "accepted": False,
              "termination_reason": "600-frame saved preparing diagnostic; independent visual and physical review pending",
              "physical_failure_flags": ["Original hand or vehicle pixels, qualification and physical completion need independent review"],
              "trace_reference": "trace.jsonl", "video_references": [view + ".mkv" for view in VIEWS],
              "video_frame_map_reference": "video_frames.jsonl",
              "recording_description": construction["recording_description"],
              "recording_evidence": [{"name": "preparing_observations", "unit": "structured",
                                      "reference": "preparing_observations.jsonl"}],
              "realized_observables": {},
              "provenance_kind": "synthetic_local_diagnostic" if synthetic else "original_native"}
    from worker_exchange.native_output import write_result
    write_result(attempt, result)
    require(all(digest(attempt / name) == expected for name, expected in hashes.items()),
            "Recorded-only finalizer changed original acquisition")
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.output)
