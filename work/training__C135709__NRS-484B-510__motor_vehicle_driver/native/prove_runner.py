"""CPU checks for exact Native request and telemetry geometry helpers."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from types import SimpleNamespace

from capture_plan import CASES, build
from runner import body, check, execute, speed


class Actor:
    def __init__(self):
        self.bounding_box = SimpleNamespace(extent=SimpleNamespace(x=2.0, y=1.0))

    def get_transform(self):
        return SimpleNamespace(location=SimpleNamespace(x=5.0, y=-2.5),
                               rotation=SimpleNamespace(yaw=0.0))

    def get_velocity(self):
        return SimpleNamespace(x=3.0, y=4.0, z=0.0)


def reject(request: dict) -> str:
    try:
        check(request)
    except ValueError as exc:
        return str(exc)
    raise AssertionError("accepted altered Native request")


def prove() -> dict:
    checked = {suffix: check(build(suffix)) for suffix in CASES}
    assert len(checked) == len(CASES) == 6
    assert all(value["frames"] == 600 and not value["original_native_observed"]
               for value in checked.values())
    actor = Actor()
    assert body(actor) == [3.0, -3.5, 7.0, -1.5]
    assert speed(actor) == 5.0
    base = build("witness_1")
    negatives = {}
    for name, edit in {
            "wrong_case": ("case_id", "other"),
            "wrong_duration": ("duration_s", 31),
            "wrong_camera": ("camera_sizes", {"overview": (1, 1)}),
            "purpose_forgery": ("requested_purpose", "unrelated_purpose")}.items():
        altered = copy.deepcopy(base)
        altered[edit[0]] = edit[1]
        negatives[name] = reject(altered)
    try:
        execute(base, Path("work"), "127.0.0.1", 2000)
    except ValueError as exc:
        negatives["output_outside_scratch"] = str(exc)
    else:
        raise AssertionError("runner accepted attempt output under work")
    return {"format": "restricted-zone-native-runner-cpu-proof-v1",
            "case_ids": [value["case_id"] for value in checked.values()],
            "source_body_m": body(actor), "source_speed_mps": speed(actor),
            "negative_rejections": negatives, "carla_executed": False,
            "physical_or_legal_acceptance_claimed": False}


if __name__ == "__main__":
    print(json.dumps(prove(), sort_keys=True))
