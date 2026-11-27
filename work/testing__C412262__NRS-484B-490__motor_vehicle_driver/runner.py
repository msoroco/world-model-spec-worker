"""Source-gated C412262 Native entrypoint; CARLA imports occur only at capture."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

from highway_scene_construction import ASSIGNMENT, construct, validate_site
from native_capture import capture
from native_output_bridge import publish


ROOT = Path(__file__).resolve().parent


def check(site_path: Path | None = None, site_sha256: str | None = None) -> dict:
    config = json.loads((ROOT / "config.json").read_text())
    if config.get("assignment_id") != ASSIGNMENT or config.get("cell_id") != "C412262" or config.get("law_id") != "NRS-484B-490":
        raise ValueError("exact C412262 bundle scope mismatch")
    if hashlib.sha256((ROOT / "case-plan.json").read_bytes()).hexdigest() != config.get("plan_sha256"):
        raise ValueError("exact C412262 plan changed")
    case_id = config.get("selected_case_id")
    if case_id not in config.get("supported_case_ids", []):
        raise ValueError("selected case outside bundled scope")
    if site_path is not None or site_sha256 is not None:
        if site_path is None or site_sha256 is None:
            raise ValueError("source-hashed reviewed highway site required")
        if hashlib.sha256(site_path.read_bytes()).hexdigest() != site_sha256:
            raise ValueError("reviewed highway site source hash mismatch")
        validate_site(site_path, case_id)
    return {"case_id": case_id, "site_sha256": site_sha256}


def load_operator(path: Path, sha256: str):
    if hashlib.sha256(path.read_bytes()).hexdigest() != sha256:
        raise ValueError("reviewed Native operator source hash mismatch")
    spec = importlib.util.spec_from_file_location("reviewed_parking_operator", path)
    if spec is None or spec.loader is None:
        raise ValueError("reviewed Native operator cannot load")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, "make_adapter", None)):
        raise ValueError("reviewed Native operator factory missing")
    return module


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    if args.check:
        selected = check()
        print(selected["case_id"])
        return
    site_name = os.environ.get("SCENARIO_HIGHWAY_SITE_PACKET")
    site_hash = os.environ.get("SCENARIO_HIGHWAY_SITE_SHA256")
    if not site_name or not site_hash:
        raise ValueError("source-hashed reviewed highway site required")
    site_path = Path(site_name).resolve()
    selected = check(site_path, site_hash)
    operator_name = os.environ.get("SCENARIO_HIGHWAY_OPERATOR_MODULE")
    operator_hash = os.environ.get("SCENARIO_HIGHWAY_OPERATOR_SHA256")
    if not args.output_dir or not operator_name or not operator_hash:
        raise ValueError("Native output and source-hashed reviewed operator required")
    operator = load_operator(Path(operator_name).resolve(), operator_hash)
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30.0)
    world = client.get_world()
    adapter = operator.make_adapter(world, json.loads(site_path.read_text()), selected["case_id"])
    built = construct(adapter, site_path, selected["case_id"])
    try:
        site = validate_site(site_path, selected["case_id"])
        capture(world, adapter, site, selected["case_id"], args.output_dir, site_hash)
        publish(args.output_dir, map_bytes=adapter.map_bytes(world), restored=True)
    finally:
        for actor in reversed(built["owned"]):
            adapter.destroy(actor)


if __name__ == "__main__":
    main()
