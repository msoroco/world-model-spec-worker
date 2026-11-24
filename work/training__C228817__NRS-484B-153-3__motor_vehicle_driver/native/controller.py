"""Deterministic 20 Hz door and passing-vehicle requests for two planned probes.

These requests need Native actuator and observation wiring before delivery.
"""

CASES = {"closes_after_transfer": 212, "remains_open": 400}
FRAMES = 600
FPS = 20


def request(case: str, frame: int) -> dict:
    if case not in CASES or type(frame) is not int or not 0 <= frame < FRAMES:
        raise ValueError("known case and 600-frame index required")
    close_frame = CASES[case]
    return {
        "frame": frame, "time_s": frame / FPS,
        "ego_hold_brake": 1.0,
        "traffic_side_door_request": "open" if 100 <= frame < close_frame else "closed",
        "transfer_request": "passenger_board" if frame == 200 else "none",
        "passing_vehicle_request": "pass_ego_left" if 110 <= frame <= 210 else "none",
        "target_only": True,
    }


def verify_schedule() -> dict:
    timelines = {case: [request(case, i) for i in range(FRAMES)] for case in CASES}
    a, b = timelines.values()
    assert sum(r["traffic_side_door_request"] == "open" for r in a) == 112
    assert sum(r["traffic_side_door_request"] == "open" for r in b) == 300
    assert all(x["transfer_request"] == y["transfer_request"] and
               x["passing_vehicle_request"] == y["passing_vehicle_request"] and
               x["ego_hold_brake"] == y["ego_hold_brake"] for x, y in zip(a, b))
    return {"frames_per_case": FRAMES, "fps": FPS, "fixed_request_fields":
            ["ego_hold_brake", "transfer_request", "passing_vehicle_request"],
            "deliberate_difference": "traffic_side_door_request closing frame",
            "closing_frames": CASES, "native_completion": "unverified"}


if __name__ == "__main__":
    import json
    print(json.dumps(verify_schedule(), sort_keys=True))
