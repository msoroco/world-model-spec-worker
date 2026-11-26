"""Canonical C157964 dispatch to a reviewed-site Native capture adapter."""

import argparse
import importlib
import json
import os
from pathlib import Path

from native_capture import capture
from preflight_native_site import preflight
from yield_view import CASES, require


ASSIGNMENT = "testing__C157964__NRS-484B-257-1__motor_vehicle_driver"


def selected(config, case_id):
    require(case_id in config["supported_case_ids"], "unselected exact yield case")
    case = next((item for item in CASES if case_id == ASSIGNMENT + "__" + item.case_id), None)
    require(case is not None, "unknown exact yield case")
    require(config["law_id"] == "NRS-484B-257-1" and
            config["cell_id"] == "C157964" and
            config["actor"] == "motor_vehicle_driver", "canonical yield identity differs")
    return case


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", default=os.getenv("SCENARIO_CASE_ID"))
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--host", default=os.getenv("CARLA_HOST"))
    parser.add_argument("--port", default=os.getenv("CARLA_PORT"))
    parser.add_argument("--site", type=Path)
    parser.add_argument("--source-root", type=Path)
    parser.add_argument("--adapter-module", default=os.getenv("C157964_ADAPTER_MODULE", "native_adapter"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text())
    case = selected(config, args.case)
    if args.check:
        print(ASSIGNMENT + "__" + case.case_id)
        return
    require(args.output_dir and args.host and args.port and args.site and
            args.source_root and args.adapter_module,
            "reviewed original site, Native adapter, CARLA host/port and output are required")
    preflight(args.site, args.source_root, case.case_id)
    module = importlib.import_module(args.adapter_module)
    adapter = module.create_adapter(config, args.host, int(args.port))
    print(json.dumps(capture(adapter, args.site, args.source_root,
                             args.output_dir, case), sort_keys=True))


if __name__ == "__main__":
    main()
