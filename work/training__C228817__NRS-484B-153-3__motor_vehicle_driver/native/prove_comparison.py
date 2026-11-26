"""CPU-only regression for the independent door comparison audit."""

import copy
import hashlib
import json
from pathlib import Path

from audit_comparison import compare
from measure_door import VIEWS
from prove_door import fixture

ASSIGNMENT = "training__C228817__NRS-484B-153-3__motor_vehicle_driver"


def pair(kind="passenger"):
    packets = [fixture(212, kind), fixture(400, kind)]
    context = {
        "map_source_sha256": "synthetic-map", "road_id": 1,
        "ego_blueprint": "synthetic-sedan", "passing_blueprint": "synthetic-sedan",
        "traffic_lane_id": -1, "ego_spawn": [10.0, -1.75],
        "passing_spawn": [0.0, 1.75], "transfer_kind": kind,
        "transfer_frame": 200, "camera_plan_sha256": "synthetic-camera-plan",
        "controller_policy_sha256": "synthetic-controller-policy",
        "fps": 20, "frame_count": 600, "camera_names": list(VIEWS),
    }
    for index, packet in enumerate(packets, 1 if kind == "passenger" else 3):
        packet["case_id"] = f"{ASSIGNMENT}__probe_{index}"
        packet["source_sha256"] = f"synthetic-trace-{index}"
        packet["construction_context"] = copy.deepcopy(context)
        for name in VIEWS:
            packet["cameras"][name]["sha256"] = f"synthetic-{name}-{index}"
    return packets


def main():
    reference, contrast = pair()
    positive = compare(reference, contrast)
    assert positive["measured_close_difference_s"] == 9.4
    assert positive["post_transfer_open_s"] == [0.6, 10.0]
    cargo_reference, cargo_contrast = pair("cargo")
    cargo_positive = compare(cargo_reference, cargo_contrast)
    assert cargo_positive["measured_close_difference_s"] == 9.4
    assert cargo_positive["post_transfer_open_s"] == [0.6, 10.0]
    negatives = {}
    mutations = {
        "road_changed": lambda a, b: b["construction_context"].update(road_id=2),
        "camera_plan_changed": lambda a, b: b["construction_context"].update(camera_plan_sha256="other"),
        "passing_spawn_changed": lambda a, b: b["construction_context"].update(passing_spawn=[9.0, 1.75]),
        "transfer_changed": lambda a, b: b["transfer_events"][0].update(native_frame=201),
        "no_difference": lambda a, b: b["frames"].__setitem__(slice(None), copy.deepcopy(a["frames"])),
        "same_trace": lambda a, b: b.update(source_sha256=a["source_sha256"]),
        "same_camera": lambda a, b: b["cameras"]["overview"].update(sha256=a["cameras"]["overview"]["sha256"]),
        "wrong_side": lambda a, b: b["door"].update(side="right"),
    }
    for kind in ("passenger", "cargo"):
        for label, mutate in mutations.items():
            a, b = pair(kind)
            mutate(a, b)
            try:
                compare(a, b)
            except ValueError as error:
                negatives[kind + ":" + label] = str(error)
            else:
                raise AssertionError("negative comparison accepted: " + kind + ":" + label)
    root = Path(__file__).resolve().parent
    report = {
        "format": "synthetic-door-comparison-proof", "passed": True,
        "positive": {"passenger": positive, "cargo": cargo_positive},
        "negative_rejections": negatives,
        "source_code_sha256": hashlib.sha256((root / "audit_comparison.py").read_bytes()).hexdigest(),
        "limitations": ["Synthetic traces and camera hashes only; physical completion and legal necessity remain unverified"],
    }
    (root / "comparison-proof.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"two comparisons measured 9.4 s difference; {len(negatives)} negatives rejected")


if __name__ == "__main__":
    main()
