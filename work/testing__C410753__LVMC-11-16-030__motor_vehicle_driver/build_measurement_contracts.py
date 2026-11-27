"""Bind each selected rail target to the original sources its audit must reopen."""
from __future__ import annotations

import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
ORIGINALS = [
    "native-rail-receipt.json",
    "reviewed-rail-packet.json",
    "native-rail-frames.json",
    "native-rail-camera-map.json",
    "original-frames/*",
    "original-rays/*",
    "original-exceptions/*",
    "original-cameras/*",
]


def build():
    plan = json.loads((HERE / "case-plan.json").read_text())
    if plan.get("assignment_id") != ASSIGNMENT or len(plan.get("cases", [])) != 7:
        raise ValueError("selected railway plan identity or count differs")
    for case in plan["cases"]:
        case_id = case["case_id"]
        key = case_id.removeprefix(ASSIGNMENT + "__")
        if case_id != ASSIGNMENT + "__" + key or not key.isidentifier():
            raise ValueError("selected railway case identity differs")
        folder = HERE / "cases" / key
        folder.mkdir(parents=True, exist_ok=True)
        definitions = {
            0: ("traversal_speed_and_sight", "measure_traversal_sight",
                ["native-rail-frames.json", "reviewed-rail-packet.json"]),
            1: ("flagman_duty_state", "measure_flagman",
                ["native-rail-frames.json", "reviewed-rail-packet.json"]),
            2: ("signal_installation_visibility_and_warning", "measure_signal",
                ["native-rail-frames.json", "reviewed-rail-packet.json"]),
        }
        requirements = []
        for index, disposition in enumerate(plan["requirement_dispositions"]):
            if case_id not in disposition["case_ids"]:
                continue
            output_key, method, inputs = definitions[index]
            requirements.append({
                "disposition_index": index,
                "requirement": disposition["requirement"],
                "source": disposition["source"],
                "output_key": output_key, "method": method,
                "value_type": "object", "kind": "measured",
                "inputs": inputs,
            })
        contract = {
            "format": "worker-measurement-contract",
            "case_id": case_id,
            "original_capture": {"fps": 20, "duration_s": 45,
                                 "frame_count": 900,
                                 "camera_views": ["overview", "approach",
                                                  "track_left", "track_right"]},
            "engineering_target": {
                "traversal_mph": case["engineering_target_traversal_mph"],
                "sight_setup": case["engineering_sight_setup"],
                "exception_setup": case["exception_setup"],
                "is_observed_outcome": False,
            },
            "requirements": requirements,
            "negative": {"remove": ["native-rail-frames.json"],
                         "error_contains": "Missing required source: native-rail-frames.json"},
            "physical_completion_confirmed": False,
            "legal_conclusion": None,
            "limitations": [
                "The engineering target does not establish measured speed, sight or exception state.",
                "A CPU fixture cannot establish CARLA motion, pixel quality or legal visibility.",
            ],
            "required_original_sources": ORIGINALS,
        }
        (folder / "measurement-contract.json").write_text(
            json.dumps(contract, indent=2, sort_keys=True) + "\n")
    return len(plan["cases"])


if __name__ == "__main__":
    print(build())
