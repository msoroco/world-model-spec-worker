"""Exact C386411 bus-stop position construction and source-gated Native entry."""
from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path


def check() -> dict:
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text())
    scene = json.loads((root / "scene.json").read_text())
    case = config["case"]
    if (config["law_id"] != "LVMC-11-60-030-A1" or config["cell_id"] != "C386411" or
            config["actor"] != "bus_driver" or config["selected_case_id"] != scene["case_id"] or
            case["case_id"] != scene["case_id"]):
        raise ValueError("exact bus-stop position identity changed")
    if config["rate_hz"] != 20 or config["duration_s"] != 45 or len(config["cameras"]) != 4:
        raise ValueError("position/camera capture contract changed")
    if scene["source_kind"] != "synthetic_diagnostic_fixture" or scene["cell_id"] != "C386411":
        raise ValueError("diagnostic scene source identity changed")
    if scene["conduct"] != case["conduct"] or scene["location_relation"] != case["location_relation"]:
        raise ValueError("case activity/location target changed")
    if case["location_relation"] not in ("inside", "outside") or case["conduct"] not in ("stand", "park"):
        raise ValueError("unknown exact stop-position case")
    return scene


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--site")
    parser.add_argument("--adapter-module")
    parser.add_argument("--host")
    parser.add_argument("--port")
    args = parser.parse_args()
    scene = check()
    if args.check:
        print("exact diagnostic bus-stop position check passed: " + scene["case_id"])
        return
    site = args.site or os.environ.get("C386411_REVIEWED_SITE")
    module = args.adapter_module or os.environ.get("C386411_NATIVE_ADAPTER_MODULE")
    if not site or not module or not args.output_dir:
        raise ValueError("reviewed original site, attested Native adapter and output required")
    from native_capture import capture
    adapter = importlib.import_module(module).create_adapter(scene["case_id"], args.host, args.port)
    print(json.dumps(capture(adapter, Path(site), scene["case_id"], Path(args.output_dir)), sort_keys=True))


if __name__ == "__main__":
    main()
