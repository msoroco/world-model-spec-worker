"""Exact C135087 source-gated Native acquisition entrypoint."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

from native_capture import capture, validate_survey

HERE = Path(__file__).resolve().parent


def check() -> str:
    config = json.loads((HERE / "config.json").read_text())
    plan_bytes = (HERE / "case-plan.json").read_bytes()
    if hashlib.sha256(plan_bytes).hexdigest() != config["plan_sha256"]:
        raise ValueError("exact case plan source changed")
    plan = json.loads(plan_bytes)
    case_id = config["selected_case_id"]
    if case_id not in {row["case_id"] for row in plan["cases"]}:
        raise ValueError("selected case absent from exact plan")
    if config["assignment_id"] != "testing__C135087__NRS-484B-153-3__motor_vehicle_driver" or config["cell_id"] != "C135087" or config["law_id"] != "NRS-484B-153-3":
        raise ValueError("bundle scope mismatch")
    return case_id


def _module(path: Path, expected_sha256: str):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError("reviewed Native operator hash mismatch")
    spec = importlib.util.spec_from_file_location("reviewed_door_operator", path)
    if spec is None or spec.loader is None:
        raise ValueError("reviewed Native operator cannot load")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    case_id = check()
    if args.check:
        print(case_id)
        return
    if not args.host or not args.port or not args.output_dir:
        raise ValueError("Native host, port and output directory required")
    survey_path = os.environ.get("SCENARIO_DOOR_SURVEY_PACKET")
    survey_sha256 = os.environ.get("SCENARIO_DOOR_SURVEY_SHA256")
    operator_path = os.environ.get("SCENARIO_DOOR_OPERATOR_MODULE")
    operator_sha256 = os.environ.get("SCENARIO_DOOR_OPERATOR_SHA256")
    if not all((survey_path, survey_sha256, operator_path, operator_sha256)):
        raise ValueError("source-hashed reviewed site and operator required")
    survey = Path(survey_path).resolve()
    raw = survey.read_bytes()
    if hashlib.sha256(raw).hexdigest() != survey_sha256:
        raise ValueError("reviewed site source hash mismatch")
    validate_survey(json.loads(raw), case_id)
    module = _module(Path(operator_path).resolve(), operator_sha256)
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    world = client.get_world()
    hooks = module.make_hooks(world, json.loads(raw), case_id)
    names = ("map_reader", "actor_factory", "door_controller", "loading_controller",
             "original_observer", "camera_factory")
    if not isinstance(hooks, dict) or any(not callable(hooks.get(name)) for name in names):
        raise ValueError("reviewed operator missing required Native hooks")
    config = json.loads((HERE / "config.json").read_text())
    result = capture(world, case_id=case_id, survey_path=survey,
                     survey_sha256=survey_sha256, output=args.output_dir,
                     door_open_tick=config.get("door_open_tick", 120),
                     **{name: hooks[name] for name in names})
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
