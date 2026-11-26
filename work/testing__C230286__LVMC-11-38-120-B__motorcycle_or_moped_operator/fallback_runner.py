"""Exact C230286 lamp construction with original-source and readback gates.

Native execution requires a reviewed CARLA adapter. This CPU module never
claims that requested lamp output, atmospheric visibility, or photometric range
was physically realized.
"""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

from lamp_controls import prepare
from source_packet import ASSIGNMENT


HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check():
    config = json.loads((HERE / "config.json").read_text(encoding="utf-8"))
    if config.get("assignment_id") != ASSIGNMENT or config.get("law_id") != "LVMC-11-38-120-B":
        raise ValueError("lamp bundle identity mismatch")
    if config.get("cell_id") != "C230286" or config.get("actor") != "motorcycle_or_moped_operator":
        raise ValueError("lamp bundle fixed cell or actor mismatch")
    plan_path = HERE / "case-plan.json"
    if sha(plan_path) != config.get("plan_sha256"):
        raise ValueError("selected lamp plan changed")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    case = next((row for row in plan["cases"] if row["case_id"] == config["selected_case_id"]), None)
    if case is None or set(config["supported_case_ids"]) != {row["case_id"] for row in plan["cases"]}:
        raise ValueError("selected exact lamp case missing")
    if config.get("rate_hz") != 20 or config.get("duration_s") != 30:
        raise ValueError("20 Hz thirty-second source capture required")
    return case


def _load(path):
    spec = importlib.util.spec_from_file_location("c230286_reviewed_adapter", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    case = check()
    if args.check:
        print(case["case_id"])
        return
    if not args.host or not args.port or not args.output_dir:
        raise ValueError("Native host, port and output directory required")
    packet = os.environ.get("SCENARIO_LAMP_SOURCE_PACKET")
    packet_sha = os.environ.get("SCENARIO_LAMP_SOURCE_SHA256")
    adapter_path = os.environ.get("SCENARIO_LAMP_NATIVE_ADAPTER")
    adapter_sha = os.environ.get("SCENARIO_LAMP_NATIVE_ADAPTER_SHA256")
    if not all((packet, packet_sha, adapter_path, adapter_sha)):
        raise ValueError("reviewed source packet and Native adapter required")
    if sha(packet) != packet_sha or sha(adapter_path) != adapter_sha:
        raise ValueError("reviewed Native source or adapter bytes changed")
    adapter_module = _load(adapter_path)
    if not callable(getattr(adapter_module, "make_adapter", None)):
        raise ValueError("reviewed Native adapter factory required")
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30)
    adapter = adapter_module.make_adapter(client.get_world(), case["case_id"], camera_offset_m=2.0)
    for method in ("snapshot_settings", "configure_sync", "readback_sync",
                   "loaded_map_bytes", "sha_bytes", "verify_sidewalk",
                   "spawn_vehicle", "vehicle_blueprint_id", "set_lamps",
                   "read_lamps", "set_weather", "read_weather", "set_route",
                   "capture", "destroy_owned", "restore_settings", "readback_restored"):
        if not callable(getattr(adapter, method, None)):
            raise ValueError("Native adapter callback absent: " + method)
    original_settings = adapter.snapshot_settings()
    restored = False
    try:
        adapter.configure_sync(rate_hz=20)
        if adapter.readback_sync(rate_hz=20) is not True:
            raise ValueError("Native 20 Hz readback failed")
        selected = prepare(adapter, packet, HERE / "case-plan.json")
        outcome = adapter.capture(selected["ego"], args.output_dir, frames=600)
        if outcome.get("case_id") != case["case_id"] or outcome.get("frame_count") != 600:
            raise ValueError("original synchronized 600-frame capture incomplete")
    finally:
        adapter.destroy_owned()
        adapter.restore_settings(original_settings)
        restored = adapter.readback_restored(original_settings) is True
    if not restored:
        raise ValueError("Native world settings restoration readback failed")
    print(json.dumps({"case_id": case["case_id"], "original_frames": 600,
                      "physical_acceptance": "unverified"}, sort_keys=True))


if __name__ == "__main__":
    main()
