"""CPU test of exact door command transitions and original-source guards."""

import copy
import hashlib
import json
import os
from pathlib import Path

from door_actuation import apply_door_command, command, validate_review, validate_setup
from runner import check as check_runner


def _write(root, name, value):
    path = root / name
    path.write_text(json.dumps(value, sort_keys=True) + "\n")
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


class FakeVehicle:
    def __init__(self):
        self.calls = []

    def open_door(self, door):
        self.calls.append(("open", door))

    def close_door(self, door):
        self.calls.append(("closed", door))


def main():
    root = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", ".runtime-work")) / "c228817-actuation-fixture"
    root.mkdir(parents=True, exist_ok=True)
    map_record = {"map_name": "Town03"}
    road_record = {"map_name": "Town03",
                   "frozen_cell": {"layout": "road", "maneuver": "load_unload", "control": "other_vehicle"},
                   "door_side": "left", "passing_side": "left",
                   "driver_actor_id": "driver-1", "door_operator_actor_id": "driver-1",
                   "passing_actor_id": "passing-2",
                   "passing_lateral_offsets_m": [2.0] * 600}
    transfer = {"kind": "passenger", "frame": 200,
                "pedestrian_actor_id": "pedestrian-3", "occupancy_delta": 1}
    review = {"source_kind": "original_native_scene_review",
              "sources": {"map": _write(root, "map.json", map_record),
                          "road": _write(root, "road.json", road_record),
                          "transfer": _write(root, "transfer.json", transfer)}}
    accepted = []
    for case, close in (("closes_after_transfer", 212), ("remains_open", 400)):
        checked = validate_review(review, case)
        vehicle = FakeVehicle()
        for frame in range(600):
            row = apply_door_command(vehicle, "FL", case, frame)
            assert row["observed_door_open"] is None
        assert vehicle.calls == [("closed", "FL"), ("open", "FL"), ("closed", "FL")]
        assert command(case, close - 1)["door_command"] == "open"
        assert command(case, close)["door_command"] == "closed"
        accepted.append({"case": case, "closing_frame": close,
                         "command_transitions": vehicle.calls,
                         "source_hashes": checked["source_hashes"]})
    negatives = []
    for label, mutate, error in (
        ("wrong_side", lambda r: r.update(door_side="right"), "traffic side"),
        ("other_operator", lambda r: r.update(door_operator_actor_id="other"), "driver"),
        ("wrong_transit", lambda r: r.update(passing_lateral_offsets_m=[-2.0] * 600), "Passing actor"),
        ("missing_path", lambda r: r.update(map_name="OtherTown"), "map and road"),
    ):
        changed = copy.deepcopy(road_record)
        mutate(changed)
        bad = copy.deepcopy(review)
        bad["sources"]["road"] = _write(root, label + ".json", changed)
        try:
            validate_review(bad, "closes_after_transfer")
        except ValueError as exc:
            assert error in str(exc), (label, str(exc))
            negatives.append(label)
        else:
            raise AssertionError("Guard did not reject " + label)
    missing = copy.deepcopy(review)
    missing["sources"]["transfer"]["path"] = str(root / "absent.json")
    try:
        validate_review(missing, "closes_after_transfer")
    except ValueError as exc:
        assert "Original transfer source missing" in str(exc)
        negatives.append("missing_transfer_source")
    else:
        raise AssertionError("Missing transfer source was accepted")
    stale = copy.deepcopy(review)
    stale["sources"]["road"]["sha256"] = "0" * 64
    try:
        validate_review(stale, "closes_after_transfer")
    except ValueError as exc:
        assert "Original road source hash differs" in str(exc)
        negatives.append("changed_road_source")
    else:
        raise AssertionError("Changed original road source was accepted")
    cargo = {"kind": "cargo", "frame": 200, "cargo_actor_id": "crate-4"}
    cargo_review = copy.deepcopy(review)
    cargo_review["sources"]["transfer"] = _write(root, "cargo.json", cargo)
    assert validate_review(cargo_review, "remains_open")["transfer_kind"] == "cargo"
    bad_cargo = copy.deepcopy(cargo_review)
    cargo.pop("cargo_actor_id")
    bad_cargo["sources"]["transfer"] = _write(root, "cargo-missing.json", cargo)
    try:
        validate_review(bad_cargo, "remains_open")
    except ValueError as exc:
        assert "identified cargo" in str(exc)
        negatives.append("unidentified_cargo")
    else:
        raise AssertionError("Unidentified cargo was accepted")
    native = {"source_kind": "source_bound_native_setup", "sources": review["sources"],
              "native_setup": {"ego_spawn_index": 0, "passing_spawn_index": 1,
                               "walker_spawn_index": 2, "door": "FL"}}
    assert validate_setup(native, "closes_after_transfer")["door_side"] == "left"
    wrong_native = copy.deepcopy(native)
    wrong_native["native_setup"]["door"] = "FR"
    try:
        validate_setup(wrong_native, "closes_after_transfer")
    except ValueError as exc:
        assert "Native door differs" in str(exc)
        negatives.append("wrong_native_door")
    else:
        raise AssertionError("Wrong Native door was accepted")
    config_root = Path(__file__).resolve().parent
    for index in (1, 2):
        config = json.loads((config_root / f"config-probe-{index}.json").read_text())
        assert check_runner(config)["frames"] == 600
        bad_config = copy.deepcopy(config)
        bad_config["door_state_observed_by_command"] = True
        try:
            check_runner(bad_config)
        except ValueError as exc:
            assert "Command cannot establish" in str(exc)
        else:
            raise AssertionError("Actuator command was treated as observation")
    return {"format": "c228817-door-actuation-cpu-proof", "positive_cases": accepted,
            "negative_guards": negatives, "physical_completion": False,
            "legal_verdict": None}


if __name__ == "__main__":
    print(json.dumps(main(), sort_keys=True))
