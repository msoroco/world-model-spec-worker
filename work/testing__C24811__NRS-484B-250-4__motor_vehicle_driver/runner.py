"""Lazy Native entrypoint for source-reviewed inoperative-signal cases."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

import native_signal as signal


HERE = Path(__file__).resolve().parent


def check():
    config = json.loads((HERE / "config.json").read_text())
    plan = (HERE / "case-plan.json").read_bytes()
    if hashlib.sha256(plan).hexdigest() != config["plan_sha256"]:
        raise ValueError("exact inoperative-signal plan changed")
    if config.get("assignment_id") != signal.ASSIGNMENT or \
            config.get("law_id") != "NRS-484B-250-4" or \
            config.get("cell_id") != "C24811" or \
            config.get("catalog_control") != "traffic_light":
        raise ValueError("exact inoperative-signal bundle scope changed")
    selected = config["selected_case_id"]
    case = next((item for item in signal.CASES
                 if selected == signal.ASSIGNMENT + "__" + item.name), None)
    if case is None:
        raise ValueError("selected case outside frozen assignment")
    return config, case


def _reviewed(path_string, expected):
    if not path_string or not expected:
        raise ValueError("source-hashed reviewed signal site and operator required")
    path = Path(path_string).resolve()
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
        raise ValueError("reviewed source bytes changed")
    return path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    config, case = check()
    if args.check:
        print(config["selected_case_id"])
        return
    if not args.host or not args.port or not args.output_dir:
        raise ValueError("Native host, port and output directory required")
    site_path = _reviewed(os.environ.get("SCENARIO_SIGNAL_SITE_PACKET"),
                          os.environ.get("SCENARIO_SIGNAL_SITE_SHA256"))
    operator_path = _reviewed(os.environ.get("SCENARIO_SIGNAL_OPERATOR_MODULE"),
                              os.environ.get("SCENARIO_SIGNAL_OPERATOR_SHA256"))
    site = json.loads(site_path.read_text())
    signal.validate_site(site, site_path, case)
    spec = importlib.util.spec_from_file_location("reviewed_signal_operator", operator_path)
    if spec is None or spec.loader is None:
        raise ValueError("reviewed Native operator cannot load")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "make_operator", None)):
        raise ValueError("reviewed Native operator factory missing")
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    world = client.get_world()
    operator = module.make_operator(world, site, case.name)
    from native_capture import capture
    from native_output_bridge import publish
    capture(world, case=case, site=site, site_path=site_path,
            output=args.output_dir, operator=operator,
            brake_distance_m=config.get("brake_distance_m", 12.0))
    publish(args.output_dir, map_bytes=operator.map_bytes(world), restored=True)


if __name__ == "__main__":
    main()
