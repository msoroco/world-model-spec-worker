"""Synthetic source-shaped regression; no CARLA motion or acceptance claim."""

import hashlib
import json
from pathlib import Path

from measure_door import FRAME_COUNT, VIEWS, measure


def fixture(close_frame=212, transfer_kind="passenger"):
    rows = [
        {"native_frame": i, "native_time_s": i / 20, "door_open": 100 <= i < close_frame,
         "door_state_source_ref": "synthetic:door-pose", "ego_speed_mps": 0.0,
         "ego_motion_source_ref": "synthetic:ego-transform"}
        for i in range(FRAME_COUNT)
    ]
    event = {"kind": transfer_kind, "native_frame": 200, "source_ref": "synthetic:transfer"}
    if transfer_kind == "passenger":
        event.update(occupancy_delta=1, pedestrian_actor_id="ped-1")
    else:
        event.update(cargo_actor_id="box-1")
    return {
        "source_kind": "native_trace", "source_sha256": "synthetic-diagnostic-only",
        "cameras": {n: {"frame_count": FRAME_COUNT, "sha256": "synthetic-" + n} for n in VIEWS},
        "driver_actor_id": "ego", "door_operator_actor_id": "ego",
        "door": {"side": "left", "source_ref": "synthetic:door-hinge"},
        "passing_vehicle": {"actor_id": "passing-1", "source_ref": "synthetic:actor-history",
                            "lateral_offsets_m": [3.4] * FRAME_COUNT,
                            "transit_frames": list(range(110, 211))},
        "frames": rows, "transfer_events": [event],
    }


def main():
    near = measure(fixture())
    extended = measure(fixture(400))
    cargo = measure(fixture(260, "cargo"))
    shifted = fixture()
    for i, row in enumerate(shifted["frames"]):
        row["native_frame"] = i + 5480
        row["native_time_s"] = 274.0 + i / 20
        row["video_frame"] = i
    shifted["transfer_events"][0]["native_frame"] = 5680
    shifted["transfer_events"][0]["video_frame"] = 200
    shifted_measure = measure(shifted)
    assert shifted_measure["first_native_tick"] == 5480
    assert shifted_measure["last_transfer_frame"] == 200
    assert near["post_transfer_open_s"] == 0.6
    assert extended["post_transfer_open_s"] == 10.0
    assert cargo["transfer_kinds"] == ["cargo"]
    assert near["legal_necessity"] == "unresolved_requires_contextual_review"
    negatives = {}
    mutations = {
        "missing_camera": lambda p: p["cameras"].pop("approach"),
        "missing_frame": lambda p: p["frames"].pop(),
        "nonmonotone_frame": lambda p: p["frames"][300].update(native_frame=299),
        "wrong_video_join": lambda p: p["frames"][300].update(video_frame=299),
        "unsourced_door": lambda p: p["frames"][150].update(door_state_source_ref=""),
        "wrong_side": lambda p: p["door"].update(side="right"),
        "ambiguous_path": lambda p: p["passing_vehicle"]["lateral_offsets_m"].__setitem__(150, -3.4),
        "wrong_operator": lambda p: p.update(door_operator_actor_id="other"),
        "no_transfer": lambda p: p.update(transfer_events=[]),
        "unsourced_transfer": lambda p: p["transfer_events"][0].update(source_ref=""),
        "moving_vehicle": lambda p: p["frames"][150].update(ego_speed_mps=2.0),
        "truncated_door": lambda p: p["frames"].__setitem__(slice(400, None), [dict(r, door_open=True) for r in p["frames"][400:]]),
    }
    for name, mutation in mutations.items():
        packet = fixture()
        mutation(packet)
        try:
            measure(packet)
        except ValueError as exc:
            negatives[name] = str(exc)
        else:
            raise AssertionError(f"negative {name} accepted")
    root = Path(__file__).resolve().parent
    proof = {
        "format": "synthetic-native-door-diagnostic-proof", "passed": True,
        "source_code_sha256": hashlib.sha256((root / "measure_door.py").read_bytes()).hexdigest(),
        "positive": {"close_after_transfer": near, "extended_open": extended,
                     "cargo": cargo, "nonzero_original_tick": shifted_measure},
        "negative_rejections": negatives,
        "limitations": ["Synthetic trace only; no CARLA original frame map or camera pixels",
                        "necessity and immediacy are unresolved legal judgments",
                        "fixture source refs are deliberately not original Native hashes"],
    }
    (root / "door-proof.json").write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")
    print(f"4 positives, {len(negatives)} source and geometry negatives passed")


if __name__ == "__main__":
    main()
