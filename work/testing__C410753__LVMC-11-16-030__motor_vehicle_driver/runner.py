"""Canonical exact railway case entrypoint and Native operator interface."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

from rail_construction import TARGETS
from rail_native_runner import run_case


def load_case(path=None):
    scene = json.loads(Path(path or Path(__file__).with_name("scene.json")).read_text())
    key = scene.get("case_key")
    if (key not in TARGETS or
            scene.get("assignment_id") !=
            "testing__C410753__LVMC-11-16-030__motor_vehicle_driver" or
            scene.get("case_id") != scene["assignment_id"] + "__" + key or
            scene.get("cell_id") != "C410753" or
            scene.get("law_id") != "LVMC-11-16-030" or
            scene.get("actor") != "motor_vehicle_driver" or
            scene.get("target_mph") != TARGETS[key][0] or
            scene.get("obscured_sight_target") is not TARGETS[key][1] or
            scene.get("exception_target") != TARGETS[key][2] or
            scene.get("duration_frames") != 900 or
            scene.get("rate_hz") != 20):
        raise ValueError("exact railway case identity or target differs")
    return scene


def run_native(*, case_path, packet, attempt_root, world, ego,
               location_factory, transform_factory, original_exception_reader,
               camera_adapter, control_factory, brake):
    """Run only with operator-supplied original Native sources and adapters."""
    scene = load_case(case_path)
    if packet.get("assignment_id") != scene["assignment_id"]:
        raise ValueError("rail packet assignment differs")
    return run_case(
        case_key=scene["case_key"], packet=packet, attempt_root=attempt_root,
        world=world, ego=ego, location_factory=location_factory,
        transform_factory=transform_factory,
        original_exception_reader=original_exception_reader,
        camera_adapter=camera_adapter, control_factory=control_factory,
        brake=brake)


def _reviewed_file(path_value, checksum, label):
    if not path_value or not checksum:
        raise ValueError("source-hashed reviewed railway " + label + " required")
    path = Path(path_value).resolve()
    if (not path.is_file() or path.is_symlink() or
            hashlib.sha256(path.read_bytes()).hexdigest() != checksum):
        raise ValueError("reviewed railway " + label + " source changed")
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", type=Path, default=Path(__file__).with_name("scene.json"))
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    scene = load_case(args.case)
    if args.check:
        print(json.dumps({"case_id": scene["case_id"],
                          "offline_identity_checked": True,
                          "original_native_site_required_at_capture": True}))
        return
    if not args.host or not args.port or not args.output_dir:
        raise ValueError("railway Native host, port and output directory required")
    packet_path = _reviewed_file(os.environ.get("SCENARIO_RAIL_SITE_PACKET"),
                                 os.environ.get("SCENARIO_RAIL_SITE_SHA256"),
                                 "site packet")
    operator_path = _reviewed_file(os.environ.get("SCENARIO_RAIL_OPERATOR_MODULE"),
                                   os.environ.get("SCENARIO_RAIL_OPERATOR_SHA256"),
                                   "operator module")
    packet = json.loads(packet_path.read_text())
    if packet.get("assignment_id") != scene["assignment_id"]:
        raise ValueError("reviewed railway site packet assignment differs")
    spec = importlib.util.spec_from_file_location("reviewed_rail_operator", operator_path)
    if spec is None or spec.loader is None:
        raise ValueError("reviewed railway Native operator cannot load")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    factory = getattr(module, "make_operator", None)
    if not callable(factory):
        raise ValueError("reviewed railway Native operator factory missing")
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    world = client.get_world()
    operator = factory(world, packet, scene["case_key"])
    required = ("ego", "location_factory", "transform_factory",
                "original_exception_reader", "camera_adapter",
                "control_factory", "brake")
    if not isinstance(operator, dict) or any(key not in operator for key in required):
        raise ValueError("reviewed railway Native operator capabilities missing")
    run_native(case_path=args.case, packet=packet, attempt_root=args.output_dir,
               world=world, **{key: operator[key] for key in required})


if __name__ == "__main__":
    main()
