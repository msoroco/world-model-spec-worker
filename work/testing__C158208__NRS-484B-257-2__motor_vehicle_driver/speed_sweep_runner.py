"""Source-gated Native runner for staged crossing-speed engineering points."""
from __future__ import annotations

import argparse
import importlib
import json
from pathlib import Path

from native_capture import capture
from yield_site import validate_site

HERE = Path(__file__).resolve().parent


def check(root: Path) -> dict:
    config = json.loads((root / "config.json").read_text())
    extension = json.loads((root / "speed-sweep-extension.json").read_text())
    if config.get("selected_case_id") not in {row["case_id"] for row in extension["cases"]}:
        raise ValueError("speed sweep offline case identity differs")
    if config.get("rate_hz") != 20 or config.get("frame_count") != 900 or \
            config.get("duration_s") != 45 or len(config.get("cameras", [])) != 4:
        raise ValueError("speed sweep capture profile differs")
    return config


def prepare(case_id: str, site_path: Path, adapter=None) -> dict:
    extension = json.loads((HERE / "speed-sweep-extension.json").read_text())
    cases = [row for row in extension["cases"] if row["case_id"] == case_id]
    if extension.get("status") != "construction_staged_proofs_pending" or len(cases) != 1:
        raise ValueError("exact staged crossing-speed case required")
    validate_site(site_path, case_id)
    if adapter is not None and (not callable(getattr(adapter, "supports_speed_target", None)) or
                                adapter.supports_speed_target() is not True):
        raise ValueError("Native adapter lacks original speed-target control")
    anchor = json.loads((HERE / "cases/approaching_near_response/config.json").read_text())
    config = dict(anchor)
    config["selected_case_id"] = case_id
    config["supported_case_ids"] = [case_id]
    config["case"] = dict(anchor["case"], case_id=case_id,
                          draft_variables=cases[0]["draft_variables"])
    config["control"] = dict(anchor["control"],
                             requested_ego_crossing_speed_mps=cases[0]["draft_variables"][
                                 "requested_ego_crossing_speed_mps"])
    config["diagnostic_only"] = False
    return config


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--case")
    parser.add_argument("--site", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--adapter-module")
    parser.add_argument("--host")
    parser.add_argument("--port")
    args = parser.parse_args()
    if args.check:
        config = check(HERE)
        print(config["selected_case_id"])
        raise SystemExit(0)
    if not all((args.case, args.site, args.output, args.adapter_module)):
        raise ValueError("exact case, reviewed site, output and Native adapter required")
    module = importlib.import_module(args.adapter_module)
    config = prepare(args.case, args.site)
    adapter = module.create_adapter(config, args.host, args.port)
    if not callable(getattr(adapter, "supports_speed_target", None)) or \
            adapter.supports_speed_target() is not True:
        raise ValueError("Native adapter lacks original speed-target control")
    print(json.dumps(capture(adapter, config, args.site, args.output), sort_keys=True))
