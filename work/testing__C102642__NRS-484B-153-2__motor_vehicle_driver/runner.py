"""Exact door-action diagnostic entrypoint."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
from site_contract import CASE_ACTIONS
from site_contract import read_packet, validate_site
from native_capture import CAMERAS, RATE_HZ, FRAME_COUNT
from native_runner import run_capture


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text())
    source = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(source).hexdigest() != config["plan_sha256"]:
        raise ValueError("case plan source changed")
    plan = json.loads(source)
    case = config["selected_case_id"]
    if case not in {row["case_id"] for row in plan["cases"]}:
        raise ValueError("selected case absent from exact plan")
    kind = case.removeprefix(config["assignment_id"] + "__")
    if kind not in CASE_ACTIONS or tuple(config["action"]) != CASE_ACTIONS[kind]:
        raise ValueError("selected door act/side differs")
    camera_names = tuple(item["name"] if isinstance(item, dict) else item for item in config["cameras"])
    if config["rate_hz"] != RATE_HZ or config["frame_count"] != FRAME_COUNT or len(camera_names) != len(CAMERAS) or len(set(camera_names)) != len(CAMERAS):
        raise ValueError("original camera or duration profile differs")
    return case


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    case = check()
    if args.check:
        print("diagnostic door bundle passed: " + case)
        return
    if not args.output_dir or not args.host or not args.port:
        raise ValueError("Native host, port and output directory are required")
    survey_name = os.environ.get("SCENARIO_DOOR_SURVEY_PACKET")
    survey_hash = os.environ.get("SCENARIO_DOOR_SURVEY_SHA256")
    operator_name = os.environ.get("SCENARIO_DOOR_OPERATOR_MODULE")
    operator_hash = os.environ.get("SCENARIO_DOOR_OPERATOR_SHA256")
    if not all((survey_name, survey_hash, operator_name, operator_hash)):
        raise ValueError("original survey and source-hashed operator module are required")
    survey = Path(survey_name).resolve()
    packet = read_packet(survey, survey_hash)
    validate_site(packet, case.removeprefix(json.loads((Path(__file__).resolve().parent / "config.json").read_text())["assignment_id"] + "__"))
    operator = Path(operator_name).resolve()
    if hashlib.sha256(operator.read_bytes()).hexdigest() != operator_hash:
        raise ValueError("operator module source hash mismatch")
    spec = importlib.util.spec_from_file_location("door_operator", operator)
    if spec is None or spec.loader is None:
        raise ValueError("operator module cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30.0)
    world = client.get_world()
    hooks = module.make_hooks(world, packet, case)
    required = {"actor_factory", "driver_act_controller", "original_observer"}
    if not isinstance(hooks, dict) or not required <= hooks.keys() or not all(callable(hooks[key]) for key in required):
        raise ValueError("operator module did not supply three Native hooks")
    map_reader = hooks.get("map_reader", lambda native_world: native_world.get_map().to_opendrive().encode("utf-8"))
    if not callable(map_reader):
        raise ValueError("operator map reader must be callable")
    try:
        result = run_capture(world, carla, survey_path=survey, survey_sha256=survey_hash,
                             case_id=case, output=Path(args.output_dir), map_reader=map_reader,
                             actor_factory=hooks["actor_factory"],
                             driver_act_controller=hooks["driver_act_controller"],
                             original_observer=hooks["original_observer"])
    except Exception as error:
        # The runtime retains a failed Native attempt only with an explicit
        # failure status. Never turn an incomplete acquisition into success.
        status = Path(args.output_dir) / "native-run-status.json"
        status.write_text(json.dumps({"errors": [str(error)], "case_id": case,
                                      "capture_complete": False}, sort_keys=True) + "\n")
        raise
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
