"""C104538 authored Native proposal and synthetic source meter, not a capture."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SIGN = {"id": "c104538-no-u-turn-1", "code": "no_u_turn",
        "governs_road": 1, "governs_lane": -1, "station_m": 42.0,
        "authorization_proven": False, "scope": "authored proposal"}
VARIANTS = {
    "primary": {"start_x_m": -35.0, "turn_start_frame": 220, "scripted_visibility": .9},
    "fallback1": {"start_x_m": -50.0, "turn_start_frame": 220, "scripted_visibility": .9},
    "fallback2": {"start_x_m": -35.0, "turn_start_frame": 225, "scripted_visibility": .9},
    "fallback3": {"start_x_m": -35.0, "turn_start_frame": 220, "scripted_visibility": 1.0},
}
KINDS = ("mounted_obey", "mounted_turn", "dismounted_turn")


def parameters(kind: str, name: str) -> dict:
    """Native capture policy; the saved trigger rows remain synthetic only."""
    if kind not in ("mounted_obey", "mounted_turn") or name not in VARIANTS:
        raise ValueError("Unknown mounted Native construction")
    from geometry import native_route
    return {"case_suffix": kind, "candidate_id": name,
            "native_route_xy_m": native_route(kind, VARIANTS[name]["start_x_m"]),
            "start_x_m": VARIANTS[name]["start_x_m"],
            "release_frame": VARIANTS[name]["turn_start_frame"],
            "target_speed_mps": 3.5 if name == "fallback1" else 5.0,
            "lookahead_m": 5.5 if name == "fallback2" else 4.0,
            "sign_camera_xyz_m": [-12, 11, 6] if name == "fallback3" else [-12, 9, 5],
            "rate_hz": 20, "duration_s": 24,
            "actor_blueprint": "vehicle.bh.crossbike", "selected": False}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def position(kind: str, variant: dict, frame: int) -> tuple[float, float]:
    start = variant["turn_start_frame"]
    x0 = variant["start_x_m"]
    if frame < start:
        return x0 + (0-x0)*frame/start, 4.0
    if kind == "mounted_obey":
        return min(30.0, (frame-start)*.12), 4.0
    if frame <= start+80:
        a = math.pi/2 - math.pi*(frame-start)/80
        return 4*math.cos(a), 4*math.sin(a)
    return max(-25.0, -(frame-start-80)*.12), -4.0


def make_rows(kind: str, name: str) -> list[dict]:
    if kind not in KINDS or name not in VARIANTS:
        raise ValueError("Unknown construction")
    v = VARIANTS[name]
    rows = []
    for frame in range(480):
        x, y = position(kind, v, frame)
        mounted = kind != "dismounted_turn" or frame < 200
        turn = kind != "mounted_obey" and v["turn_start_frame"] <= frame <= v["turn_start_frame"]+80
        rows.append({"frame": frame, "time_s": frame/20, "actor_id": "rider-1",
                     "machine_id": "bicycle-1", "machine_class": "bicycle",
                     "sign_id": SIGN["id"], "road_id": 1, "approach_lane_id": -1,
                     "mounted": mounted, "walking_machine": not mounted,
                     "u_turn_active": turn, "x_m": round(x, 6), "y_m": round(y, 6),
                     "scripted_visibility": v["scripted_visibility"]})
    return rows


def measure(rows: list[dict], sign: dict, name: str) -> dict:
    if len(rows) != 480 or [r["frame"] for r in rows] != list(range(480)):
        raise ValueError("Frame join failed")
    if any(r["time_s"] != r["frame"]/20 for r in rows):
        raise ValueError("Time join failed")
    if sign["id"] != "c104538-no-u-turn-1" or sign["code"] != "no_u_turn":
        raise ValueError("Sign source changed")
    if any(r["sign_id"] != sign["id"] or r["road_id"] != sign["governs_road"]
           or r["approach_lane_id"] != sign["governs_lane"] for r in rows):
        raise ValueError("Sign/actor approach join failed")
    turns = [r for r in rows if r["u_turn_active"]]
    mounted_turns = sum(r["mounted"] for r in turns)
    dismounted_turns = len(turns)-mounted_turns
    if turns and turns[0]["frame"] < 200:
        raise ValueError("Dismount ordering unproved")
    if any(r["walking_machine"] == r["mounted"] for r in rows):
        raise ValueError("Posture contradiction")
    v = VARIANTS[name]
    runway = -v["start_x_m"]-8
    return {"frames": 480, "turn_frames": len(turns),
            "mounted_turn_frames": mounted_turns,
            "dismounted_turn_frames": dismounted_turns,
            "first_turn_frame": turns[0]["frame"] if turns else None,
            "dismount_frame": next((r["frame"] for r in rows if not r["mounted"]), None),
            "approach_runway_m": runway,
            "release_error_frames": v["turn_start_frame"]-220,
            "scripted_visibility": v["scripted_visibility"],
            "runway_trigger_under_35m": runway < 35,
            "release_trigger_over_3_frames": v["turn_start_frame"]-220 > 3,
            "visibility_trigger_below_0_95": v["scripted_visibility"] < .95,
            "native_sign_authorized": False, "original_native_observed": False,
            "legal_outcome": "unresolved"}


def write_sources() -> dict:
    out = ROOT/"draft-native-sources"
    out.mkdir(exist_ok=True)
    sign_path = out/"authored-sign.json"
    sign_path.write_text(json.dumps(SIGN, indent=2, sort_keys=True)+"\n")
    entries = []
    for kind in KINDS:
        for name in VARIANTS:
            rows = make_rows(kind, name)
            path = out/f"{kind}-{name}.jsonl"
            path.write_text("".join(json.dumps(r, sort_keys=True, separators=(",", ":"))+"\n" for r in rows))
            entries.append({"kind": kind, "variant": name, "path": str(path.relative_to(ROOT)),
                            "sha256": digest(path), "measurement": measure(rows, SIGN, name)})
    return {"format": "c104538-lvmc-1140080-synthetic-source-v1",
            "scope": "unselected synthetic CPU diagnostic", "sign_path": str(sign_path.relative_to(ROOT)),
            "sign_sha256": digest(sign_path), "entries": entries}


if __name__ == "__main__":
    manifest = write_sources()
    target = ROOT/"draft-native-source-manifest.json"
    target.write_text(json.dumps(manifest, indent=2, sort_keys=True)+"\n")
    print(json.dumps({"entries": len(manifest["entries"]), "manifest_sha256": digest(target)}))
