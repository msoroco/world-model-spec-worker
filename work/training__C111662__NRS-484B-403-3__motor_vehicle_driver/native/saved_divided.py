"""Synthetic raw-to-saved measurement for the divided-highway opening branch."""
import json
import math
from pathlib import Path

from build import POLICIES, RATE, put, sha
from divided_opening import BRANCH, CENTERS, FRAMES, OPENING_X, check
from saved import body


def make_raw(bundle):
    bundle = Path(bundle)
    cfg = json.loads((bundle / "config.json").read_text())
    requests = [json.loads(line) for line in
                (bundle / "requested-tracks.jsonl").read_text().splitlines()]
    output = []
    for i, request in enumerate(requests):
        center = request["requested_ego_xyz_m"]
        next_center = requests[min(i + 1, FRAMES - 1)]["requested_ego_xyz_m"]
        velocity = [round((next_center[k] - center[k]) * RATE, 6) for k in range(3)]
        output.append({
            "frame": i, "video_frame": i, "request_frame": i,
            "time_s": request["time_s"], "source_kind": "synthetic_fixture",
            "ego": {"actor_id": 10, "blueprint": cfg["ego_blueprint"],
                    "center_xyz_m": center,
                    "heading_rad": request["requested_heading_rad"],
                    "velocity_xyz_mps": velocity,
                    "speed_mps": round(math.sqrt(sum(v*v for v in velocity)), 6),
                    "body_xyz_m": body(center, request["requested_heading_rad"])},
            "requested_phase": request["requested_phase"],
            "authored_divided_highway": True,
            "median_open_at_crossing": request["median_open_at_crossing"],
            "district_designation_verified": False,
            "opening_exception_legally_verified": False,
            "original_native_observed": False, "legal_verdict": None})
    return {"format": "c111662-4033-divided-synthetic-raw-v1",
            "case_id": cfg["case_id"], "candidate_id": cfg["candidate_id"],
            "config_sha256": sha(bundle / "config.json"),
            "tracks_sha256": sha(bundle / "requested-tracks.jsonl"),
            "rows": output, "synthetic": True, "original_native_observed": False}


def process(bundle, raw_path):
    bundle, raw_path = Path(bundle), Path(raw_path)
    check(bundle)
    cfg = json.loads((bundle / "config.json").read_text())
    raw = json.loads(raw_path.read_text())
    if raw != make_raw(bundle) or len(raw.get("rows", [])) != FRAMES:
        raise ValueError("Divided branch actor, body or video join changed")
    rows = raw["rows"]
    turn = [row for row in rows if row["requested_phase"] == "u_turn"]
    crossing = next((row for row in turn if row["ego"]["center_xyz_m"][1] >= 0), None)
    departure = next((row for row in rows
                      if row["requested_phase"] == "westbound_departure"), None)
    if crossing is None or departure is None or len(turn) < 90 or \
            abs(departure["ego"]["heading_rad"] - math.pi) > .001:
        raise ValueError("Divided branch U-turn measurement missing")
    x = crossing["ego"]["center_xyz_m"][0]
    in_opening = OPENING_X[0] <= x <= OPENING_X[1]
    if in_opening != cfg["case_id"].endswith("__divided_opening"):
        raise ValueError("Divided branch opening status changed")
    return {"format": "c111662-4033-divided-synthetic-saved-v1",
            "case_id": cfg["case_id"], "candidate_id": cfg["candidate_id"],
            "raw_sha256": sha(raw_path), "frames_joined": FRAMES,
            "crossing_frame": crossing["frame"], "crossing_x_m": x,
            "crossing_in_authored_opening": in_opening,
            "heading_reversal_rad": departure["ego"]["heading_rad"],
            "pre_turn_stationary_frames": sum(
                row["requested_phase"] == "pre_turn_dwell" for row in rows),
            "district_designation_verified": False,
            "opening_exception_legally_verified": False,
            "synthetic": True, "original_native_observed": False,
            "legal_verdict": None, "delivery_ready": False}


def build():
    entries = []
    for suffix in CENTERS:
        for candidate in POLICIES:
            bundle = BRANCH / "drafts" / suffix / candidate
            raw = BRANCH / "synthetic" / suffix / candidate / "raw.json"
            saved = raw.parent / "saved.json"
            put(raw, make_raw(bundle))
            put(saved, process(bundle, raw))
            entries.append({"case_suffix": suffix, "candidate_id": candidate,
                            "raw_sha256": sha(raw), "saved_sha256": sha(saved)})
    put(BRANCH / "saved-manifest.json", {
        "format": "c111662-4033-divided-synthetic-saved-manifest-v1",
        "entries": entries, "original_native_observed": False})
    return entries


if __name__ == "__main__":
    print(json.dumps({"processed": len(build())}))
