"""Synthetic curved-grade sightline diagnostic; never original visibility evidence."""
import json
import math
from pathlib import Path
from prove import HERE, RADIUS, check, inverse_point, curve_point, elevation, put, sha

DISTANCE_M = 152.4
STEP = 0.1


def station_table():
    cumulative = [0.0]
    for i in range(4500):
        station = (i + .5) * STEP
        grade = .8 * (200 - station) / 20000
        cumulative.append(cumulative[-1] + STEP * math.sqrt(1 + grade * grade))
    return cumulative


TABLE = station_table()


def distance_at(station):
    cell = station / STEP
    low = min(4499, max(0, int(cell)))
    return TABLE[low] + (cell - low) * (TABLE[low + 1] - TABLE[low])


def station_at(distance):
    import bisect
    if distance < 0 or distance > TABLE[-1]:
        return None
    low = min(4499, bisect.bisect_right(TABLE, distance) - 1)
    return low * STEP + STEP * (distance - TABLE[low]) / (TABLE[low + 1] - TABLE[low])


def observers(subject_station):
    distance = distance_at(subject_station)
    return [round(station_at(distance + direction * DISTANCE_M), 6)
            if station_at(distance + direction * DISTANCE_M) is not None else None
            for direction in (-1, 1)]


def ray_margin(subject_xyz, observer_station):
    """Road ribbon above a 1.4 m eye-to-center sample, at 101 chord samples."""
    if observer_station is None:
        return None
    ox, oy = curve_point(observer_station, 1.75)
    oz = elevation(observer_station, .8) + 1.4
    sx, sy, sz = subject_xyz
    margins = []
    for i in range(101):
        part = i / 100
        x, y = ox + part * (sx - ox), oy + part * (sy - oy)
        station, offset = inverse_point(x, y)
        if 0 <= station <= 450 and abs(offset) <= 4.5:
            ray_z = oz + part * (sz + 1.4 - oz)
            margins.append(elevation(station, .8) - ray_z)
    return round(max(margins), 6) if margins else None


def make_raw(bundle):
    bundle = Path(bundle)
    cfg = json.loads((bundle / "config.json").read_text())
    requests = [json.loads(line) for line in (bundle / "requested-tracks.jsonl").read_text().splitlines()]
    rows = []
    for request in requests:
        subject = request["requested_ego_xyz_m"]
        station, _ = inverse_point(*subject[:2])
        eyes = observers(station)
        rows.append({"frame": request["frame"], "requested_ego_xyz_m": subject,
                     "subject_road_station_m": round(station, 6),
                     "observer_road_stations_m": eyes,
                     "observer_road_distances_m": [round(abs(distance_at(station) - distance_at(eye)), 6)
                                                   if eye is not None else None for eye in eyes],
                     "analytic_road_above_ray_m": [ray_margin(subject, eye) for eye in eyes]})
    return {"format": "c104496-curve-synthetic-ray-raw-v1", "case_id": cfg["case_id"],
            "candidate_id": cfg["candidate_id"], "config_sha256": sha(bundle / "config.json"),
            "tracks_sha256": sha(bundle / "requested-tracks.jsonl"), "rows": rows,
            "synthetic": True, "original_native_observed": False,
            "human_visibility_reviewed": False}


def process(bundle, raw_path):
    bundle, raw_path = Path(bundle), Path(raw_path)
    check(bundle)
    cfg = json.loads((bundle / "config.json").read_text())
    raw = json.loads(raw_path.read_text())
    if (raw.get("format") != "c104496-curve-synthetic-ray-raw-v1" or
            raw.get("case_id") != cfg["case_id"] or raw.get("candidate_id") != cfg["candidate_id"] or
            raw.get("config_sha256") != sha(bundle / "config.json") or
            raw.get("tracks_sha256") != sha(bundle / "requested-tracks.jsonl") or
            raw.get("synthetic") is not True or raw.get("original_native_observed") is not False or
            raw.get("human_visibility_reviewed") is not False):
        raise ValueError("Synthetic source or provenance changed")
    expected = make_raw(bundle)
    if raw != expected:
        raise ValueError("Synthetic frame join, curved station, distance or ray changed")
    requests = [json.loads(line) for line in (bundle / "requested-tracks.jsonl").read_text().splitlines()]
    turn = [row for row, request in zip(raw["rows"], requests)
            if request["requested_motion_phase"] in ("forward_left", "reverse_right", "forward_left_finish")]
    clear = sum(all(m is not None and m <= 0 for m in row["analytic_road_above_ray_m"]) for row in turn)
    result = {"format": "c104496-curve-synthetic-saved-v1", "case_id": cfg["case_id"],
              "candidate_id": cfg["candidate_id"], "raw_sha256": sha(raw_path),
              "config_sha256": sha(bundle / "config.json"), "frames_joined": len(raw["rows"]),
              "turn_frames": len(turn), "analytic_both_clear_turn_frames": clear,
              "analytic_road_above_ray_turn_frames": len(turn) - clear,
              "minimum_clear_fraction": round(clear / len(turn), 6) if turn else None,
              "trigger_slow_if_clear_fraction_below": .95,
              "trigger_overview_if_original_pixel_review_missing": True,
              "trigger_stop_if_original_500ft_body_rays_missing": True,
              "synthetic": True, "original_native_observed": False,
              "human_visibility_reviewed": False, "legal_verdict": None,
              "delivery_ready": False}
    return result


def build_saved():
    entries = []
    for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
        bundle = HERE / "drafts" / "probe_03" / candidate
        raw_path = HERE / "synthetic" / "probe_03" / candidate / "raw.json"
        saved_path = raw_path.parent / "saved.json"
        put(raw_path, make_raw(bundle))
        put(saved_path, process(bundle, raw_path))
        entries.append({"candidate_id": candidate, "raw_sha256": sha(raw_path),
                        "saved_sha256": sha(saved_path)})
    put(HERE / "saved-manifest.json", {"format": "c104496-curve-synthetic-saved-manifest-v1",
                                      "entries": entries, "original_native_observed": False})
    return entries


if __name__ == "__main__":
    print(json.dumps({"processed": len(build_saved())}))
