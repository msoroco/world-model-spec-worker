"""Exact C378132 bus loading-stop construction and source-gated Native entry."""
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
    if (config["law_id"] != "LVMC-11-60-030-A2" or config["cell_id"] != "C378132" or
            config["actor"] != "bus_driver" or config["selected_case_id"] != scene["case_id"] or
            case["case_id"] != scene["case_id"]):
        raise ValueError("exact bus loading-stop identity changed")
    if config["rate_hz"] != 20 or config["duration_s"] != 45 or len(config["cameras"]) != 4:
        raise ValueError("loading-stop camera capture contract changed")
    if scene["source_kind"] != "synthetic_diagnostic_fixture" or scene["cell_id"] != "C378132":
        raise ValueError("diagnostic scene source identity changed")
    for key in ("location_kind", "loading_purpose", "stop_reason", "bus_class"):
        if scene[key] != case[key]:
            raise ValueError("case loading-stop target changed: " + key)
    if case["location_kind"] not in ("outside", "bus_stop", "bus_stand", "passenger_loading_zone", "route_origin", "route_destination"):
        raise ValueError("unknown exact loading location")
    if case["loading_purpose"] not in ("passenger", "baggage", "cargo_only") or case["stop_reason"] not in ("ordinary", "emergency") or case["bus_class"] not in ("regular", "tour"):
        raise ValueError("unknown purpose, reason or bus classification")
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
        print("exact diagnostic bus loading-stop check passed: " + scene["case_id"])
        return
    site = args.site or os.environ.get("C378132_REVIEWED_SITE")
    module = args.adapter_module or os.environ.get("C378132_NATIVE_ADAPTER_MODULE")
    if not site or not module or not args.output_dir:
        raise ValueError("reviewed original site, attested Native adapter and output required")
    from native_capture import capture
    adapter = importlib.import_module(module).create_adapter(scene["case_id"], args.host, args.port)
    print(json.dumps(capture(adapter, Path(site), scene["case_id"], Path(args.output_dir)), sort_keys=True))


if __name__ == "__main__":
    main()
