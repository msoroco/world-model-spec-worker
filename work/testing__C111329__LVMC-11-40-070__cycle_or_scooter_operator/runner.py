"""Exact bicycle instruction capture from reviewed local Native sources.

The adapter is installed by the local operator. Its session owns the CARLA world,
camera sensors, and restoration. No synthetic authority packet is accepted here.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
from pathlib import Path

from native_device import construct as construct_bike, read_site
from native_officer import construct as construct_officer, read_officer_source, read_command
from native_capture import capture
from native_route import command_step
from native_cameras import CAMERAS, DIMENSIONS

ROOT = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(root: Path = ROOT) -> dict:
    config = json.loads((root / "config.json").read_text())
    plan_path = root / "case-plan.json"
    if sha(plan_path) != config.get("plan_sha256"):
        raise ValueError("exact case plan hash mismatch")
    plan = json.loads(plan_path.read_text())
    case_id = config.get("selected_case_id")
    matches = [row for row in plan["cases"] if row["case_id"] == case_id]
    if len(matches) != 1:
        raise ValueError("selected exact case unavailable")
    case = matches[0]
    for key in ("device_type", "device_instruction", "officer_direction", "operator_motion"):
        if config.get(key) != case[key]:
            raise ValueError("exact case changed: " + key)
    if (config.get("law_id"), config.get("cell_id"), config.get("actor")) != (
            plan["law_id"], plan["cell_id"], plan["actor"]):
        raise ValueError("assignment identity changed")
    if (config.get("rate_hz"), config.get("frame_count"), config.get("duration_s")) != (20, 900, 45):
        raise ValueError("original capture time contract changed")
    if config.get("cameras") != list(CAMERAS):
        raise ValueError("four-camera plan changed")
    return case


def preflight_sources(case: dict, site_path: Path, site_sha256: str,
                      officer_path: Path | None, officer_sha256: str | None) -> dict:
    site = read_site(site_path, site_sha256)
    if site["device_type"] != case["device_type"]:
        raise ValueError("reviewed site has another device type")
    officer = None
    if case["officer_direction"] != "none":
        if officer_path is None or not officer_sha256:
            raise ValueError("reviewed Police Officer authority source required")
        raw = officer_path.read_bytes()
        if hashlib.sha256(raw).hexdigest() != officer_sha256:
            raise ValueError("original officer source hash mismatch")
        officer = json.loads(raw)
        for key in ("source_kind", "map_name", "authority_source", "officer_blueprint_id",
                    "gesture_asset_id", "spawn_xyz", "recipient_bike_id", "command",
                    "start_frame", "end_frame", "visible_camera_ids"):
            if key not in officer:
                raise ValueError("incomplete original officer source: " + key)
        if officer["source_kind"] != "original_local_officer_authority_and_gesture":
            raise ValueError("unverified original officer source")
        if officer["map_name"] != site["map_name"] or officer["authority_source"] != site.get("police_authority_source"):
            raise ValueError("officer authority differs from reviewed site")
        if officer["command"] != case["officer_direction"]:
            raise ValueError("officer direction differs from exact case")
        if not isinstance(officer["visible_camera_ids"], list) or len(set(officer["visible_camera_ids"]) & set(CAMERAS)) < 2:
            raise ValueError("reviewed officer camera plan insufficient")
    elif officer_path is not None or officer_sha256 is not None:
        raise ValueError("undeclared officer source")
    return {"site": site, "officer": officer}


def execute(config_root: Path, output_dir: Path, site_path: Path, site_sha256: str,
            officer_path: Path | None, officer_sha256: str | None,
            adapter_name: str, host: str, port: int) -> dict:
    case = check(config_root)
    sources = preflight_sources(case, site_path, site_sha256, officer_path, officer_sha256)
    if not output_dir.is_dir():
        raise ValueError("executor output directory missing")
    trace_path = output_dir / "original-instruction-trace.json"
    if trace_path.exists():
        raise ValueError("original trace already exists")
    adapter = importlib.import_module(adapter_name)
    if not hasattr(adapter, "open_session"):
        raise ValueError("Native adapter lacks open_session")
    with adapter.open_session(host, port, sources["site"], case) as session:
        world = session.world
        carla = session.carla
        built = construct_bike(world, carla, sources["site"], case)
        bike = built["bike"]
        officer = None
        try:
            if sources["officer"] is not None:
                read_officer_source(officer_path, officer_sha256, sources["site"], str(bike.id))
                officer = construct_officer(world, carla, sources["officer"], case,
                                            session.set_visible_gesture)["officer"]

            def officer_reader(snapshot, participant):
                if officer is None:
                    return {"actor_id": None, "authority_source": None,
                            "recipient_id": str(participant.id), "command": "none"}
                return read_command(officer, sources["officer"], snapshot.frame,
                                    session.read_visible_gesture, str(participant.id))

            def control(elapsed_s):
                return command_step(bike, carla, case, sources["site"], elapsed_s)

            camera_readers = {name: (lambda frame, name=name: session.read_camera(name, frame))
                              for name in CAMERAS}
            return capture(world, bike, built["device"], case, sources["site"],
                           site_sha256, session.read_device, officer_reader, trace_path,
                           camera_readers=camera_readers, camera_dimensions=DIMENSIONS,
                           control_step=control)
        finally:
            try:
                bike.set_target_velocity(carla.Vector3D(x=0.0, y=0.0, z=0.0))
            finally:
                if officer is not None:
                    officer.destroy()
                bike.destroy()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--site", type=Path, default=os.environ.get("C111329_NATIVE_SITE"))
    parser.add_argument("--site-sha256", default=os.environ.get("C111329_NATIVE_SITE_SHA256"))
    parser.add_argument("--officer-source", type=Path, default=os.environ.get("C111329_OFFICER_SOURCE"))
    parser.add_argument("--officer-sha256", default=os.environ.get("C111329_OFFICER_SOURCE_SHA256"))
    parser.add_argument("--adapter", default=os.environ.get("C111329_NATIVE_ADAPTER"))
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    case = check()
    if args.check:
        print("exact bicycle instruction bundle passed: " + case["case_id"])
        return
    if not args.output_dir or not args.site or not args.site_sha256 or not args.adapter:
        raise ValueError("reviewed Native site, its SHA-256, adapter and output required")
    execute(ROOT, args.output_dir, args.site, args.site_sha256,
            args.officer_source, args.officer_sha256, args.adapter, args.host, args.port)


if __name__ == "__main__":
    main()
