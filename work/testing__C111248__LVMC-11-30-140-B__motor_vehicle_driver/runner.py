"""Exact blind-person encounter diagnostic bundle preflight."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path
from blind_encounter import CASE_BY_ID
from native_capture import CAMERAS
from reviewed_sources import prepare


def check():
    root = Path(__file__).resolve().parent
    config = json.loads((root / "config.json").read_text())
    source = (root / "case-plan.json").read_bytes()
    if hashlib.sha256(source).hexdigest() != config["plan_sha256"]:
        raise ValueError("Exact case plan changed")
    plan = json.loads(source)
    case_id = config["selected_case_id"]
    rows = [item for item in plan["cases"] if item["case_id"] == case_id]
    if len(rows) != 1 or not case_id.startswith(config["assignment_id"] + "__"):
        raise ValueError("Exact encounter case missing")
    suffix = case_id.removeprefix(config["assignment_id"] + "__")
    if suffix not in CASE_BY_ID:
        raise ValueError("Unsupported encounter case")
    case = CASE_BY_ID[suffix]
    knobs = {key: config["case"][key] for key in ("cue", "encounter", "response", "precaution")}
    if knobs != {"cue": case.cue, "encounter": case.encounter,
                  "response": case.response, "precaution": case.precaution}:
        raise ValueError("Encounter construction knobs changed")
    if knobs != {key: rows[0][key] for key in knobs}:
        raise ValueError("Encounter differs from exact plan")
    if config["hz"] != 20 or config["frame_count"] != 900 or config["duration_s"] != 45:
        raise ValueError("Original capture timebase changed")
    if [camera["name"] for camera in config["cameras"]] != ["overview", "approach", "reference_corner", "driver_reference"]:
        raise ValueError("Original camera list changed")
    if config["approach_speed_cap_mps"] not in (1.0, 2.0) or (config["approach_speed_cap_mps"] == 1.0 and suffix != "white_contact_stop"):
        raise ValueError("Unapproved approach speed cap")
    if config["required_sources"] != ["reviewed_map_route", "blindness_attestation",
                                      "actually_carried_cue", "original_body_history",
                                      "original_camera_pixels"]:
        raise ValueError("Encounter source contract changed")
    return case_id


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--source-packet")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    case_id = check()
    if args.check:
        print("diagnostic blind-person bundle passed: " + case_id)
        return
    source_packet = args.source_packet or os.environ.get("SCENARIO_BLIND_SOURCE_PACKET")
    if source_packet:
        plan = prepare(Path(source_packet))
        if plan["case_id"] != case_id.removeprefix(json.loads((Path(__file__).resolve().parent / "config.json").read_text())["assignment_id"] + "__"):
            raise ValueError("reviewed packet exact case mismatch")
        if not args.output_dir:
            raise ValueError("Native output directory required")
        import carla
        from scenario_pipeline.worker_exchange import world_restore
        from scenario_pipeline.worker_exchange.native_output import seal_capture
        from native_factories import construction_adapter_factory, capture_adapter_factory
        from native_operation import run_native_attempt
        client = carla.Client(args.host, args.port)
        client.set_timeout(30.0)
        config = json.loads((Path(__file__).resolve().parent / "config.json").read_text())
        output = Path(args.output_dir).resolve()
        originals = output / "original-capture"
        receipt = run_native_attempt(
            client, Path(source_packet), originals,
            construction_adapter_factory=construction_adapter_factory,
            capture_adapter_factory=lambda world, plan, constructed:
                capture_adapter_factory(world, plan, constructed, client=client,
                                        output=output, case_id=case_id),
            restore_api=world_restore,
            approach_speed_cap_mps=config["approach_speed_cap_mps"])
        for source in originals.iterdir():
            if source.name == "trace.jsonl":
                continue
            target = output / source.name
            if target.exists():
                raise ValueError("Native original conflicts with materialized attempt: " + source.name)
            source.rename(target)
        shutil.rmtree(originals)
        encoders = {}
        for camera, view in (("front", "overview"), ("left", "approach"),
                             ("right", "reference_corner"), ("rear", "driver_reference")):
            command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
                       "-framerate", "20", "-pattern_type", "glob", "-i",
                       str(output / camera / "*.png"), "-c:v", "ffv1", str(output / (view + ".mkv"))]
            completed = subprocess.run(command, check=False, capture_output=True, text=True)
            encoders[view] = completed.returncode
            if completed.returncode:
                raise ValueError("Native four-view encoder failed: " + camera + " " + completed.stderr[-500:])
        (output / "acquisition-provenance.json").write_text(json.dumps({
            "provenance_kind": "native", "diagnostic_fixture": False,
            "source_packet": str(Path(source_packet).resolve()),
            "physical_acceptance_claimed": False}, sort_keys=True) + "\n")
        seal_capture(output, frames=receipt["original_frame_count"],
                     restoration=receipt["world_restore"], errors=[],
                     encoder_exit_codes=encoders,
                     context={"reviewed_source_bindings": receipt["reviewed_source_bindings"]})
        print(json.dumps(receipt, sort_keys=True))
        return
    raise ValueError("Reviewed Native map, blindness and actually carried cue sources required")


if __name__ == "__main__":
    main()
