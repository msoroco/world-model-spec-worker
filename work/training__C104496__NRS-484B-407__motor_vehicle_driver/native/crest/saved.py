"""Process synthetic analytic sightlines; original Native observations remain separate."""
import json
import bisect
import functools
import math
from pathlib import Path
from build import CASES, HERE, POLICIES, elevation, put, sha
from check import check

DISTANCE_M = 152.4
EYE_HEIGHT_M = 1.4
BODY_SAMPLE_HEIGHT_M = 1.4


@functools.lru_cache(maxsize=4)
def roadway_stations(height):
    """0.1 m horizontal grid of cumulative 3D roadway station distance."""
    cumulative = [0.0]
    step = .1
    for i in range(4500):
        mid = (i + .5) * step
        grade = height * (200 - mid) / 20000
        cumulative.append(cumulative[-1] + step * math.sqrt(1 + grade * grade))
    return cumulative


def observer_station(subject_x, height, direction):
    cumulative = roadway_stations(height)
    cell = subject_x * 10
    low = int(cell)
    subject_s = cumulative[low] + (cell - low) * (cumulative[low + 1] - cumulative[low])
    target_s = subject_s + direction * DISTANCE_M
    if target_s < 0 or target_s > cumulative[-1]:
        return None
    index = bisect.bisect_right(cumulative, target_s) - 1
    return round((index + (target_s - cumulative[index]) /
                  (cumulative[index + 1] - cumulative[index])) / 10, 6)


def ray_margin(subject_x, observer_x, grade_height):
    """Max road height above eye-to-body segment, sampled at 101 points."""
    start = elevation(observer_x, grade_height) + EYE_HEIGHT_M
    end = elevation(subject_x, grade_height) + BODY_SAMPLE_HEIGHT_M
    return max(elevation(observer_x + (subject_x - observer_x) * i / 100, grade_height) -
               (start + (end - start) * i / 100) for i in range(101))


def process(bundle, raw_path):
    bundle, raw_path = Path(bundle), Path(raw_path)
    checked = check(bundle)
    cfg = json.loads((bundle / "config.json").read_text())
    raw = json.loads(raw_path.read_text())
    suffix, candidate = cfg["case_id"].split("__")[-1], cfg["candidate_id"]
    if (raw.get("format") != "c104496-synthetic-ray-raw-v1" or
            raw.get("synthetic") is not True or raw.get("config_sha256") != sha(bundle / "config.json") or
            raw.get("tracks_sha256") != sha(bundle / "requested-tracks.jsonl") or
            raw.get("case_id") != cfg["case_id"] or raw.get("candidate_id") != candidate or
            raw.get("original_native_observed") is not False or raw.get("human_visibility_reviewed") is not False):
        raise ValueError("Raw source, status or synthetic provenance changed")
    requests = [json.loads(x) for x in (bundle / "requested-tracks.jsonl").read_text().splitlines()]
    if len(raw.get("rows", [])) != len(requests):
        raise ValueError("Raw/request frame count changed")
    measured = []
    for row, request in zip(raw["rows"], requests):
        if row.get("frame") != request["frame"] or row.get("requested_ego_xyz_m") != request["requested_ego_xyz_m"]:
            raise ValueError("Raw/request frame or pose join changed")
        x = request["requested_ego_xyz_m"][0]
        stations = [observer_station(x, CASES[suffix], -1),
                    observer_station(x, CASES[suffix], 1)]
        expected = [round(ray_margin(x, station, CASES[suffix]), 6) if station is not None else None
                    for station in stations]
        if row.get("observer_stations_m") != stations:
            raise ValueError("500-foot roadway stations changed")
        if row.get("analytic_road_above_ray_m") != expected:
            raise ValueError("Synthetic line-of-sight measurement changed")
        measured.append({"frame": request["frame"], "phase": request["requested_motion_phase"],
                         "synthetic_road_above_ray_m": expected})
    turn = [r for r in measured if r["phase"] in ("forward_left", "reverse_right", "forward_left_finish")]
    clear = sum(all(m <= 0 for m in r["synthetic_road_above_ray_m"]) for r in turn)
    blocked = len(turn) - clear
    return {"format": "c104496-synthetic-saved-v1", "case_id": checked["case_id"],
            "candidate_id": candidate, "raw_sha256": sha(raw_path), "config_sha256": sha(bundle / "config.json"),
            "frames_joined": len(measured), "turn_frames": len(turn),
            "analytic_both_clear_turn_frames": clear, "analytic_road_above_ray_turn_frames": blocked,
            "minimum_clear_fraction": round(clear / len(turn), 6) if turn else None,
            "trigger_slow_if_clear_fraction_below": 0.95,
            "trigger_overview_if_original_pixel_review_missing": True,
            "trigger_stop_if_original_500ft_body_rays_missing": True,
            "synthetic": True, "original_native_observed": False,
            "human_visibility_reviewed": False, "legal_verdict": None,
            "delivery_ready": False}


def make_raw(bundle):
    bundle = Path(bundle)
    cfg = json.loads((bundle / "config.json").read_text())
    suffix = cfg["case_id"].split("__")[-1]
    requests = [json.loads(x) for x in (bundle / "requested-tracks.jsonl").read_text().splitlines()]
    out = []
    for r in requests:
        x = r["requested_ego_xyz_m"][0]
        stations = [observer_station(x, CASES[suffix], -1),
                    observer_station(x, CASES[suffix], 1)]
        out.append({"frame": r["frame"], "requested_ego_xyz_m": r["requested_ego_xyz_m"],
                    "observer_stations_m": stations,
                    "analytic_road_above_ray_m": [round(ray_margin(x, station, CASES[suffix]), 6)
                                                  if station is not None else None
                                                  for station in stations]})
    return {"format": "c104496-synthetic-ray-raw-v1", "case_id": cfg["case_id"],
            "candidate_id": cfg["candidate_id"], "config_sha256": sha(bundle / "config.json"),
            "tracks_sha256": sha(bundle / "requested-tracks.jsonl"), "rows": out,
            "synthetic": True, "original_native_observed": False, "human_visibility_reviewed": False}


def build_saved():
    outputs = []
    for suffix in CASES:
        for candidate in POLICIES:
            bundle = HERE / "drafts" / suffix / candidate
            raw_path = HERE / "synthetic" / suffix / candidate / "raw.json"
            saved_path = raw_path.parent / "saved.json"
            put(raw_path, make_raw(bundle))
            put(saved_path, process(bundle, raw_path))
            outputs.append({"case_id": suffix, "candidate": candidate,
                            "raw_sha256": sha(raw_path), "saved_sha256": sha(saved_path)})
    put(HERE / "saved-manifest.json", {"format": "c104496-synthetic-saved-manifest-v1",
                                      "entries": outputs, "original_native_observed": False})
    return outputs


if __name__ == "__main__":
    print(json.dumps({"processed": len(build_saved())}))
