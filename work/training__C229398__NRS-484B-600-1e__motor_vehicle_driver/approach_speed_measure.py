"""Saved-source speed diagnostic separating drive and parked phases.

The frozen cell is park/curb. This does not assert that its approach-driving
phase is a valid selected statutory case without source and scope review.
"""
import hashlib
import json
import math

ASSIGNMENT = "training__C229398__NRS-484B-600-1e__motor_vehicle_driver"
ASSIGNMENT_SHA = "e0616cb9d29d5fc1ec7b3ec53f92b82513552d2e34e18c93f28e8b64146c9726"
WITNESS_SHA = "33c9937b8dc3f00c42a8e8ac940569540fa7b8a5bd568d4cc8fb030add936ff8"
MPS_TO_MPH = 2.2369362920544


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def measure(packet_bytes, scope_bytes):
    packet, scope = json.loads(packet_bytes), json.loads(scope_bytes)
    require(packet["assignment_id"] == ASSIGNMENT and scope["assignment_id"] == ASSIGNMENT, "assignment mismatch")
    kind = packet["source_kind"]
    require(kind in {"synthetic_native_sample", "native_saved_sample"} and scope["source_kind"] == kind,
            "source kind mismatch")
    require(scope["cell_layout"] == "road" and scope["cell_maneuver"] == "park" and scope["cell_control"] == "curb",
            "frozen cell mismatch")
    require(scope["approach_phase_source_id"] and scope["curb_parking_source_id"], "temporal scope source missing")
    frames = packet["frames"]
    require(len(frames) >= 600, "recording shorter than 30 seconds")
    require(all(f["frame"] == i and abs(f["t_s"] - i / 20) < 1e-8 for i, f in enumerate(frames)),
            "noncontiguous 20 Hz frames")
    require(all(f["vehicle_id"] == packet["vehicle_id"] for f in frames), "vehicle identity changed")
    require(all(f["phase"] in {"approach_driving", "curb_parking", "parked"} for f in frames), "phase source missing")
    require(all(len(f["velocity_xyz_mps"]) == 3 and all(isinstance(v, (int, float)) and math.isfinite(v)
                for v in f["velocity_xyz_mps"]) for f in frames), "native velocity source missing")
    approach = [f for f in frames if f["phase"] == "approach_driving"]
    parked = [f for f in frames if f["phase"] == "parked"]
    require(approach and parked and approach[-1]["frame"] < parked[0]["frame"], "approach-to-park sequence missing")
    speed = lambda f: math.sqrt(sum(v * v for v in f["velocity_xyz_mps"])) * MPS_TO_MPH
    above = [f["frame"] for f in approach if speed(f) > 80.0]
    return {"format": "c229398-saved-approach-speed-diagnostic-v1",
            "assignment_id": ASSIGNMENT, "source_kind": kind,
            "frame_sha256": digest(packet_bytes), "scope_sha256": digest(scope_bytes),
            "frame_count": len(frames), "duration_s": len(frames) / 20,
            "approach_frame_range": [approach[0]["frame"], approach[-1]["frame"]],
            "parked_frame_range": [parked[0]["frame"], parked[-1]["frame"]],
            "max_approach_speed_mph": max(speed(f) for f in approach),
            "approach_frames_above_80_mph": above,
            "max_parked_speed_mph": max(speed(f) for f in parked),
            "requested_speed_used": False,
            "cell_approach_scope_verified": False,
            "legal_result": None,
            "unresolved": ["driving phase within fixed park cell", "accepted evidence measured motion", "physical velocity provenance"]}
