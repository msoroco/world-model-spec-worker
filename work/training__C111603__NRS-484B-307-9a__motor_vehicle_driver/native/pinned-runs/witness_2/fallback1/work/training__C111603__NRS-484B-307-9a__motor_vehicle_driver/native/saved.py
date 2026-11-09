"""Synthetic raw-to-saved contract for the C111603 arrow request."""
import json
import math
from pathlib import Path

from build import CASE, FRAMES, HERE, check, digest, write


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def fixture(bundle):
    """Materialize a CPU fixture, explicitly not an original CARLA capture."""
    bundle = Path(bundle)
    check(bundle)
    cfg = json.loads((bundle / "config.json").read_text())
    requested = rows(bundle / "requested-tracks.jsonl")
    return {
        "format": "c111603-3079a-synthetic-raw-v1",
        "source_kind": "synthetic_cpu_fixture", "case_id": cfg["case_id"],
        "candidate_id": cfg["candidate_id"], "config_sha256": digest(bundle / "config.json"),
        "rows": [{
            "frame": item["frame"], "time_s": item["time_s"],
            "ego_actor_id": 1603, "other_actor_id": 1604,
            "observed_ego_xyz_m": item["requested_ego_xyz_m"],
            "observed_heading_rad": item["requested_heading_rad"],
            "observed_other_vehicle_xyz_m": item["requested_other_vehicle_xyz_m"],
            "observed_signal": item["requested_signal"],
            "observed_phase": item["requested_phase"],
            "video_frame": item["frame"], "requested_frame": item["frame"]}
            for item in requested],
        "original_native_observed": False, "legal_verdict": None}


def process(bundle, raw):
    bundle = Path(bundle)
    check(bundle)
    cfg = json.loads((bundle / "config.json").read_text())
    requested = rows(bundle / "requested-tracks.jsonl")
    if (raw.get("format") != "c111603-3079a-synthetic-raw-v1" or
            raw.get("source_kind") != "synthetic_cpu_fixture" or
            raw.get("config_sha256") != digest(bundle / "config.json") or
            raw.get("case_id") != cfg["case_id"] or
            raw.get("candidate_id") != cfg["candidate_id"] or
            raw.get("original_native_observed") is not False or
            raw.get("legal_verdict") is not None):
        raise ValueError("Synthetic raw source identity changed")
    observed = raw.get("rows")
    if not isinstance(observed, list) or len(observed) != FRAMES:
        raise ValueError("Synthetic row count changed")
    holds = 0
    turn_frames = []
    for index, (request, actual) in enumerate(zip(requested, observed)):
        if (actual.get("frame") != index or actual.get("requested_frame") != index or
                actual.get("video_frame") != index or
                actual.get("time_s") != request["time_s"] or
                actual.get("ego_actor_id") != 1603 or actual.get("other_actor_id") != 1604 or
                actual.get("observed_ego_xyz_m") != request["requested_ego_xyz_m"] or
                actual.get("observed_heading_rad") != request["requested_heading_rad"] or
                actual.get("observed_other_vehicle_xyz_m") != request["requested_other_vehicle_xyz_m"] or
                actual.get("observed_signal") != request["requested_signal"] or
                actual.get("observed_phase") != request["requested_phase"]):
            raise ValueError("Synthetic frame, signal or actor join changed")
        if actual["observed_phase"] == "yield_hold":
            holds += 1
        if actual["observed_phase"] == "intersection_movement":
            turn_frames.append(actual)
    if holds < 60 or not turn_frames:
        raise ValueError("Requested yield or movement interval missing")
    first, last = turn_frames[0], turn_frames[-1]
    heading_change_deg = abs(math.degrees(last["observed_heading_rad"] - first["observed_heading_rad"]))
    right_turn = cfg["requested_movement"] == "right_arrow_turn"
    if right_turn != (heading_change_deg > 75):
        raise ValueError("Requested movement shape changed")
    return {
        "format": "c111603-3079a-synthetic-saved-v1", "case_id": cfg["case_id"],
        "candidate_id": cfg["candidate_id"], "config_sha256": digest(bundle / "config.json"),
        "row_count": FRAMES, "joined_video_frames": FRAMES,
        "observed_steady_red_with_green_right_arrow_frames": FRAMES,
        "requested_yield_hold_frames": holds,
        "measured_heading_change_deg": round(heading_change_deg, 3),
        "measured_movement_matches_arrow": right_turn,
        "other_vehicle_actor_id": 1604,
        "synthetic_cpu_fixture": True, "original_native_observed": False,
        "signal_state_originally_verified": False,
        "other_traffic_lawfulness_verified": False,
        "yield_legally_verified": False,
        "legal_verdict": None, "delivery_ready": False}


def build():
    entries = []
    for suffix in ("witness_1", "witness_2"):
        for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
            bundle = HERE / "drafts" / suffix / candidate
            output = HERE / "synthetic" / suffix / candidate
            raw = fixture(bundle)
            saved = process(bundle, raw)
            write(output / "raw.json", raw)
            write(output / "saved.json", saved)
            entries.append({"case_id": saved["case_id"], "candidate_id": candidate,
                            "raw_sha256": digest(output / "raw.json"),
                            "saved_sha256": digest(output / "saved.json")})
    result = {"format": "c111603-3079a-synthetic-saved-manifest-v1",
              "assignment_id": CASE.name, "entries": entries,
              "original_native_observed": False, "delivery_ready": False}
    write(HERE / "saved-manifest.json", result)
    return result


if __name__ == "__main__":
    print(json.dumps({"synthetic_saved": len(build()["entries"])}))
