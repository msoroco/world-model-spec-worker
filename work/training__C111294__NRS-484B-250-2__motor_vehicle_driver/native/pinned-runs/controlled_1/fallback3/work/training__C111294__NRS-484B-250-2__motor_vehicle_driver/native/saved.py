"""Source-bound synthetic entry-time measurements; no legal simultaneity verdict."""
import json
import math
from pathlib import Path
from build import CASES, FRAMES, HERE, POLICIES, RATE, put, sha
from check import check


def body(center):
    x, y, z = center
    return [[x+dx, y+dy, z+dz] for dx in (-2, 2) for dy in (-.9, .9) for dz in (-.7, .7)]


def other_body(center):
    x, y, z = center
    return [[x+dy, y+dx, z+dz] for dx in (-2, 2) for dy in (-.9, .9) for dz in (-.7, .7)]


def make_raw(bundle):
    bundle = Path(bundle)
    cfg = json.loads((bundle / "config.json").read_text())
    requests = [json.loads(line) for line in (bundle / "requested-tracks.jsonl").read_text().splitlines()]
    out = []
    for request in requests:
        out.append({"frame": request["frame"], "video_frame": request["frame"],
                    "time_s": request["time_s"], "request_frame": request["frame"],
                    "ego": {"actor_id": 10, "blueprint": cfg["ego_blueprint"],
                            "center_xyz_m": request["requested_ego_xyz_m"],
                            "body_xyz_m": body(request["requested_ego_xyz_m"]),
                            "speed_mps": request["requested_ego_speed_mps"]},
                    "other": {"actor_id": 11, "blueprint": cfg["other_blueprint"],
                              "center_xyz_m": request["requested_other_xyz_m"],
                              "body_xyz_m": other_body(request["requested_other_xyz_m"]),
                              "speed_mps": request["requested_other_speed_mps"]},
                    "authored_official_device_count": 0,
                    "original_native_observed": False, "legal_verdict": None})
    return {"format": "c111294-2502-synthetic-raw-v1", "case_id": cfg["case_id"],
            "candidate_id": cfg["candidate_id"], "config_sha256": sha(bundle / "config.json"),
            "tracks_sha256": sha(bundle / "requested-tracks.jsonl"), "rows": out,
            "synthetic": True, "original_native_observed": False,
            "human_visibility_reviewed": False}


def process(bundle, raw_path):
    bundle, raw_path = Path(bundle), Path(raw_path)
    check(bundle)
    cfg = json.loads((bundle / "config.json").read_text())
    raw = json.loads(raw_path.read_text())
    if (raw.get("format") != "c111294-2502-synthetic-raw-v1" or
            raw.get("case_id") != cfg["case_id"] or raw.get("candidate_id") != cfg["candidate_id"] or
            raw.get("config_sha256") != sha(bundle / "config.json") or
            raw.get("tracks_sha256") != sha(bundle / "requested-tracks.jsonl") or
            raw.get("synthetic") is not True or raw.get("original_native_observed") is not False or
            raw.get("human_visibility_reviewed") is not False):
        raise ValueError("Saved source or provenance changed")
    expected = make_raw(bundle)
    if raw != expected or len(raw.get("rows", [])) != FRAMES:
        raise ValueError("Frame, actor, body, source or video join changed")
    ego_entry = other_entry = None
    ego_exit = other_exit = None
    for row in raw["rows"]:
        ego = row["ego"]["body_xyz_m"]
        other = row["other"]["body_xyz_m"]
        if ego_entry is None and max(p[0] for p in ego) >= -20:
            ego_entry = row["time_s"]
        if other_entry is None and max(p[1] for p in other) >= -20:
            other_entry = row["time_s"]
        if ego_exit is None and min(p[0] for p in ego) >= 20:
            ego_exit = row["time_s"]
        if other_exit is None and min(p[1] for p in other) >= 20:
            other_exit = row["time_s"]
    if other_entry is None or other_exit is None:
        raise ValueError("Other vehicle did not traverse intersection")
    gap = None if ego_entry is None else round(ego_entry - other_entry, 6)
    return {"format": "c111294-2502-synthetic-saved-v1", "case_id": cfg["case_id"],
            "candidate_id": cfg["candidate_id"], "raw_sha256": sha(raw_path),
            "config_sha256": sha(bundle / "config.json"), "frames_joined": FRAMES,
            "ego_front_entry_s": ego_entry, "other_front_entry_s": other_entry,
            "ego_rear_exit_s": ego_exit, "other_rear_exit_s": other_exit,
            "ego_minus_other_front_entry_s": gap,
            "authored_different_highway_roads": [[250, 251, 252], [253, 254, 255]],
            "authored_official_device_count": 0,
            "trigger_slow_if_abs_entry_gap_below_s": 1.5,
            "trigger_overview_if_original_review_missing": True,
            "trigger_stop_if_original_device_or_yield_evidence_missing": True,
            "approximate_same_time_legally_determined": False,
            "official_device_governance_verified": False,
            "right_of_way_legally_determined": False,
            "synthetic": True, "original_native_observed": False,
            "legal_verdict": None, "delivery_ready": False}


def build_saved():
    entries = []
    for suffix in CASES:
        for candidate in POLICIES:
            bundle = HERE / "drafts" / suffix / candidate
            raw_path = HERE / "synthetic" / suffix / candidate / "raw.json"
            saved_path = raw_path.parent / "saved.json"
            put(raw_path, make_raw(bundle))
            put(saved_path, process(bundle, raw_path))
            entries.append({"case_id": suffix, "candidate_id": candidate,
                            "raw_sha256": sha(raw_path), "saved_sha256": sha(saved_path)})
    put(HERE / "saved-manifest.json", {"format": "c111294-2502-synthetic-saved-manifest-v1",
                                      "entries": entries, "original_native_observed": False})
    return entries


if __name__ == "__main__":
    print(json.dumps({"processed": len(build_saved())}))
