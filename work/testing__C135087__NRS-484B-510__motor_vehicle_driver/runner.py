"""Exact case entrypoint; obtains site and adapter from explicit local inputs."""

import argparse
import importlib.util
import json
import os
from pathlib import Path

from native_capture import VIEWS, capture
from restricted_zone import ZonePlan
from reviewed_site import validate
from site_geometry import load as load_native_binding


def plan_from_config(config, site_path):
    packet = json.loads(Path(site_path).read_text())
    p = dict(config["scenario_parameters"])
    p.pop("effective_conditions", None)
    p["case_id"] = config["selected_case_id"]
    p["map_id"] = packet["map_id"]
    p["restricted_source"] = "source-reviewed restricted zone"
    plan = ZonePlan(**p)
    validate(site_path, plan.case_id, plan)
    load_native_binding(site_path, plan)
    return plan


def check(config):
    if config.get("rate_hz") != 20 or config.get("frame_count") != 900:
        raise ValueError("exact 45-second 20 Hz capture required")
    if config.get("selected_case_id") not in config.get("supported_case_ids", []):
        raise ValueError("exact case selection missing")
    cameras = config.get("cameras", [])
    if [camera.get("name") for camera in cameras] != list(VIEWS):
        raise ValueError("four required camera views missing")
    if [(camera.get("width"), camera.get("height")) for camera in cameras] != \
            [(1920, 1080), (1280, 720), (1280, 720), (1280, 720)]:
        raise ValueError("camera capture profile mismatch")
    params = dict(config["scenario_parameters"])
    params.pop("effective_conditions", None)
    ZonePlan(case_id=config["selected_case_id"], map_id="checked-at-local-source",
             **params).validate()
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--site-packet", default=os.environ.get("SCENARIO_RESTRICTED_ZONE_SITE"))
    parser.add_argument("--adapter-module", default=os.environ.get("SCENARIO_RESTRICTED_ZONE_ADAPTER")
                        or str(Path(__file__).with_name("native_adapter.py")))
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    config = json.loads(Path(__file__).with_name("config.json").read_text())
    check(config)
    if args.check:
        print("exact restricted-zone construction preflight passed")
        return
    if not all((args.output_dir, args.site_packet, args.adapter_module, args.host, args.port)):
        raise ValueError("Native source packet, adapter, host, port and output required")
    plan = plan_from_config(config, args.site_packet)
    os.environ["SCENARIO_RESTRICTED_ZONE_SITE"] = str(Path(args.site_packet).resolve())
    spec = importlib.util.spec_from_file_location("local_native_adapter", args.adapter_module)
    if spec is None or spec.loader is None:
        raise ValueError("local Native adapter module unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    adapter = module.create_adapter(args.host, args.port, config, plan)
    print(json.dumps(capture(adapter, plan, args.site_packet, args.output_dir)))


if __name__ == "__main__":
    main()
