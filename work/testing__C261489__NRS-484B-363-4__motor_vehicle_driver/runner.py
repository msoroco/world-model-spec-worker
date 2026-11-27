"""Exact source-gated school-zone pass runner; --check never connects to CARLA."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path

from school_pass import ASSIGNMENT, case_name
from school_scene_construction import construct, validate_site


HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(site_path: Path | None = None, site_sha256: str | None = None) -> dict:
    config = json.loads((HERE / "config.json").read_text())
    if config.get("assignment_id") != ASSIGNMENT or config.get("cell_id") != "C261489" or config.get("law_id") != "NRS-484B-363-4":
        raise ValueError("exact school-pass bundle scope mismatch")
    if sha(HERE / "case-plan.json") != config.get("plan_sha256"):
        raise ValueError("school-pass plan source changed")
    case_id = config.get("selected_case_id")
    case_name(case_id)
    if case_id not in config.get("supported_case_ids", []):
        raise ValueError("selected school-pass case not bundled")
    if config.get("duration_s") != 45 or config.get("rate_hz") != 20 or len(config.get("cameras", [])) != 4:
        raise ValueError("four-camera 45-second capture profile missing")
    if site_path is not None or site_sha256 is not None:
        if site_path is None or site_sha256 is None or sha(site_path) != site_sha256:
            raise ValueError("source-hashed original school site required")
        validate_site(site_path, case_id)
    return {"case_id": case_id, "site_sha256": site_sha256}


def load_operator(path: Path, digest: str):
    if sha(path) != digest:
        raise ValueError("reviewed Native operator source hash mismatch")
    spec = importlib.util.spec_from_file_location("reviewed_school_pass_operator", path)
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
        print(check()["case_id"])
        return
    site_name = os.environ.get("SCENARIO_SCHOOL_PASS_SITE_PACKET")
    site_hash = os.environ.get("SCENARIO_SCHOOL_PASS_SITE_SHA256")
    operator_name = os.environ.get("SCENARIO_SCHOOL_PASS_OPERATOR_MODULE")
    operator_hash = os.environ.get("SCENARIO_SCHOOL_PASS_OPERATOR_SHA256")
    if not all((args.output_dir, site_name, site_hash, operator_name, operator_hash)):
        raise ValueError("Native output, original site and source-hashed reviewed operator required")
    site_path = Path(site_name).resolve()
    operator_path = Path(operator_name).resolve()
    selected = check(site_path, site_hash)
    operator = load_operator(operator_path, operator_hash)
    import carla
    client = carla.Client(args.host, args.port)
    client.set_timeout(30.0)
    world = client.get_world()
    site = validate_site(site_path, selected["case_id"])
    adapter = operator.make_adapter(world, site, selected["case_id"])
    built = construct(adapter, site_path, selected["case_id"])
    try:
        from native_capture import capture
        from native_output_bridge import publish
        capture(world, adapter, site, selected["case_id"], args.output_dir, site_hash)
        publish(args.output_dir, map_bytes=adapter.map_bytes(world), restored=True)
    finally:
        for actor in reversed(built["owned"]):
            adapter.destroy(actor)


if __name__ == "__main__":
    main()
