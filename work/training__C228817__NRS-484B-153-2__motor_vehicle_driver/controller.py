"""20 Hz source requests for boarding and alighting beside passing traffic.

The passing arrival schedule is an engineering comparison variable. It does
not define the statutory phrase "interfere with moving vehicular traffic".
"""

FRAMES = 600
FPS = 20
CASES = {
    "board_overlap": {"transfer": "passenger_board", "occupancy_delta": 1, "pass_start": 110},
    "board_clear": {"transfer": "passenger_board", "occupancy_delta": 1, "pass_start": 310},
    "alight_overlap": {"transfer": "passenger_alight", "occupancy_delta": -1, "pass_start": 110},
    "alight_clear": {"transfer": "passenger_alight", "occupancy_delta": -1, "pass_start": 310},
}


def request(case: str, frame: int) -> dict:
    if case not in CASES or type(frame) is not int or not 0 <= frame < FRAMES:
        raise ValueError("known case and 600-frame index required")
    spec = CASES[case]
    return {
        "frame": frame, "time_s": frame / FPS,
        "ego_hold_brake": 1.0,
        "traffic_side_door_request": "open" if 100 <= frame < 212 else "closed",
        "transfer_request": spec["transfer"] if frame == 200 else "none",
        "passing_vehicle_request": "pass_ego_left" if spec["pass_start"] <= frame <= spec["pass_start"] + 100 else "none",
        "target_only": True,
    }


def verify_schedule() -> dict:
    for transfer in ("board", "alight"):
        overlap = [request(transfer + "_overlap", i) for i in range(FRAMES)]
        clear = [request(transfer + "_clear", i) for i in range(FRAMES)]
        assert all(a["traffic_side_door_request"] == b["traffic_side_door_request"] and
                   a["transfer_request"] == b["transfer_request"] and
                   a["ego_hold_brake"] == b["ego_hold_brake"] for a, b in zip(overlap, clear))
        assert sum(x["passing_vehicle_request"] != "none" for x in overlap) == 101
        assert sum(x["passing_vehicle_request"] != "none" for x in clear) == 101
    return {"frames_per_case": FRAMES, "fps": FPS,
            "fixed_request_fields": ["ego_hold_brake", "transfer_request", "traffic_side_door_request"],
            "deliberate_difference": "passing traffic arrival window",
            "pass_start_frames": {name: spec["pass_start"] for name, spec in CASES.items()},
            "native_completion": "unverified"}
