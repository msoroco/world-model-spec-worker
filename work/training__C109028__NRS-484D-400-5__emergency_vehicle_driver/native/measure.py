"""Join 30-second emergency approach sources without treating requests as facts."""
import hashlib
import json
import math
from pathlib import Path

FRAMES = 600
RATE = 20


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Missing retained source: " + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def measure(config, native, frame_map, dispatch):
    config_path = Path(config)
    config = json.loads(config_path.read_text())
    n, m, d = rows(native), rows(frame_map), rows(dispatch)
    if config.get("frames") != FRAMES or config.get("rate_hz") != RATE:
        raise ValueError("Exact 30-second source contract differs")
    if any(len(group) != FRAMES for group in (n, m, d)):
        raise ValueError("600 retained source frames required")
    prior_frame = None
    prior_x = None
    used, response, lamp, approach = [], [], [], []
    for i, (actor, frame, call) in enumerate(zip(n, m, d)):
        native_frame = actor.get("native_frame")
        t = (i + 1) / RATE
        if type(native_frame) is not int or (prior_frame is not None and native_frame != prior_frame + 1):
            raise ValueError("Native frame sequence differs")
        prior_frame = native_frame
        if (frame.get("video_frame") != i or frame.get("native_frame") != native_frame or
                call.get("native_frame") != native_frame or
                any(type(v) not in (int, float) or abs(v - t) > 1e-4 for v in
                    (actor.get("time_s"), frame.get("time_s"), call.get("time_s")))):
            raise ValueError("Retained frame/time join differs")
        x, speed = actor.get("ego_x_m"), actor.get("ego_speed_mps")
        if (type(x) not in (int, float) or type(speed) not in (int, float) or
                not math.isfinite(x) or not math.isfinite(speed) or speed < 0 or
                (prior_x is not None and abs(x - prior_x) > speed / RATE + .5)):
            raise ValueError("Native motion source differs")
        prior_x = x
        if actor.get("source_kind") not in ("original_native", "synthetic_native_sample"):
            raise ValueError("Native provenance missing")
        if actor.get("vehicle_actor_id") != config["vehicle_actor_id"] or \
                actor.get("other_vehicle_actor_id") != config["other_vehicle_actor_id"]:
            raise ValueError("Participant identity differs")
        for key in ("siren_observed", "warning_lamp_observed"):
            if type(actor.get(key)) is not bool:
                raise ValueError("Observed signal state missing: " + key)
        if call.get("emergency_call_documented") is not None and \
                type(call["emergency_call_documented"]) is not bool:
            raise ValueError("Dispatch source state differs")
        if call.get("immediate_pursuit_documented") is not None and \
                type(call["immediate_pursuit_documented"]) is not bool:
            raise ValueError("Pursuit source state differs")
        used.append(actor["siren_observed"])
        lamp.append(actor["warning_lamp_observed"])
        response.append(call.get("emergency_call_documented") is True or
                        call.get("immediate_pursuit_documented") is True)
        approach.append(x < config["intersection_x_m"])
    if any(used) and not any(approach):
        raise ValueError("No siren approach interval")
    unauthorized = [i for i, sounding in enumerate(used) if sounding and not response[i]]
    return {"format": "c109028-source-measurement-v1", "frames": FRAMES,
            "case_id": config["case_id"], "siren_observed_frames": sum(used),
            "warning_lamp_observed_frames": sum(lamp),
            "documented_response_frames": sum(response),
            "siren_outside_documented_response_frames": len(unauthorized),
            "siren_while_approaching_frames": sum(a and s for a, s in zip(approach, used)),
            "source_hashes": {"config": sha(config_path), "native": sha(native),
                              "frame_map": sha(frame_map), "dispatch": sha(dispatch)},
            "audible_at_500_ft_verified": False,
            "authorized_emergency_vehicle_verified": False,
            "physical_legal_verdict": None}
