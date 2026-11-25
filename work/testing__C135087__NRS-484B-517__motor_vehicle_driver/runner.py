"""Exact C135087 Native entry; original site and vehicle records are mandatory."""
from __future__ import annotations

import argparse
import hashlib
import importlib
import json
from pathlib import Path
import shutil

from stand import SourceError, construct_case
from stand_capture import capture
from stand_delivery import audit as audit_delivery_sources
from stand_converter_source import audit as audit_converter_sources


HERE = Path(__file__).resolve().parent


def check(root=HERE):
    root = Path(root)
    config = json.loads((root / "config.json").read_text())
    plan_bytes = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(plan_bytes).hexdigest() != config["plan_sha256"]:
        raise SourceError("exact stand plan changed")
    plan = json.loads(plan_bytes)
    case = next((row for row in plan["cases"] if row["case_id"] == config["selected_case_id"]), None)
    if case is None or {key: case[key] for key in ("loading_mode", "entrant_mode", "access_mode")} != config["case_modes"]:
        raise SourceError("exact stand case modes changed")
    if config["assignment_id"] + "__" not in config["selected_case_id"] or config["law_id"] != "NRS-484B-517":
        raise SourceError("foreign stand case")
    if (config["fps"], config["frame_count"], config["duration_s"]) != (20, 900, 45):
        raise SourceError("stand capture timebase changed")
    expected = [("overview", 1920, 1080), ("approach", 1280, 720),
                ("reference_corner", 1280, 720), ("driver_reference", 1280, 720)]
    if [(c.get("name"), c.get("width"), c.get("height")) for c in config["cameras"]] != expected:
        raise SourceError("four stand cameras changed")
    return config, case


def run(site_ref, vehicle_ref, native_adapter, output, host="localhost", port=2000):
    config, case = check()
    if not site_ref or not vehicle_ref or not native_adapter or not output:
        raise SourceError("reviewed original stand, sign and vehicle-role records required")
    site_ref = json.loads(Path(site_ref).read_text()) if isinstance(site_ref, (str, Path)) else site_ref
    vehicle_ref = json.loads(Path(vehicle_ref).read_text()) if isinstance(vehicle_ref, (str, Path)) else vehicle_ref
    adapter_module = importlib.import_module(native_adapter)
    if not hasattr(adapter_module, "open_session"):
        raise SourceError("Native adapter has no open_session")
    root = Path(output).resolve()
    root.mkdir(parents=True, exist_ok=False)
    with adapter_module.open_session(host, port, config) as session:
        engineered = dict(case, stand_offset_m=config.get("stand_offset_m", 0.0))
        constructed = construct_case(session.adapter, site_ref, vehicle_ref, engineered)
        if constructed["case_id"] != config["selected_case_id"]:
            raise SourceError("constructed another exact case")
        for ref, name in ((site_ref, "site-original.json"),
                          (vehicle_ref, "vehicle-original.json")):
            source = Path(ref["path"])
            if source.is_symlink() or hashlib.sha256(source.read_bytes()).hexdigest() != ref["sha256"]:
                raise SourceError("reviewed original source changed")
            shutil.copy2(source, root / name)
        session.start_cameras(root, config["cameras"], constructed)
        attempt = capture(session.world, session.actors, session.observer,
                          config["selected_case_id"], constructed["site"]["map_name"],
                          root, step=session.step, camera_finalize=session.finish_cameras)
        if not hasattr(session, "export_converter_sources"):
            raise SourceError("Native adapter lacks original converter source export")
        session.export_converter_sources(root, constructed, attempt)
        source_audit = audit_converter_sources(root, attempt)
    if not session.restoration_verified:
        raise SourceError("Native world or sensor restoration unverified")
    audit_delivery_sources(root)
    (root / "converter-source-audit.json").write_text(
        json.dumps(source_audit, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    (root / "acquisition-provenance.json").write_text(json.dumps({
        "provenance_kind": "native", "diagnostic_fixture": False,
        "case_id": config["selected_case_id"]}, indent=2) + "\n")
    from worker_exchange.native_output import seal_capture
    seal_capture(root, frames=900, restoration={"restored": True,
                 "scope": "operator session closed four cameras and restored synchronous world"},
                 errors=[], encoder_exit_codes={name: 0 for name in attempt["cameras"]})
    return attempt


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--site-ref")
    parser.add_argument("--vehicle-ref")
    parser.add_argument("--native-adapter")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="localhost")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    config, _ = check()
    if args.check:
        print(config["selected_case_id"] + " source-gated bundle check passed")
        return
    run(args.site_ref, args.vehicle_ref, args.native_adapter,
        args.output_dir, args.host, args.port)


if __name__ == "__main__":
    main()
