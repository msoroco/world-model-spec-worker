"""Entry for exact parked-lamp construction bundles.

Offline mode verifies the authored case and source contract. Native mode needs
an operator supplied site packet; no source geography is synthesized here.
"""

import argparse
import json
import os
from pathlib import Path

from parked_lamps import CASES, LAW

ROOT = Path(__file__).resolve().parent


def check():
    config = json.loads((ROOT / "config.json").read_text())
    key = config["case_key"]
    if key not in CASES or config["law_id"] != LAW or config["cell_id"] != "C229398":
        raise ValueError("frozen case identity mismatch")
    if config["selected_case_id"] != config["assignment_id"] + "__" + key:
        raise ValueError("exact selected case mismatch")
    if config["rate_hz"] != 20 or config["duration_s"] != 45:
        raise ValueError("capture cadence mismatch")
    if [c["name"] for c in config["cameras"]] != ["front", "rear", "left", "right"]:
        raise ValueError("four-camera plan mismatch")
    if config["case"] != CASES[key]:
        raise ValueError("case conditions mismatch")
    return config


def native(output_dir, host, port):
    config = check()
    source = os.environ.get("PARKED_LAMP_SITE_PACKET")
    if not source:
        raise ValueError("PARKED_LAMP_SITE_PACKET source path is required for Native capture")
    from native_capture import capture, read_site
    from carla_cameras import OriginalCameras
    from worker_exchange.world_restore import snapshot, restore
    from native_closure import close
    import carla
    import hashlib

    site, _, _ = read_site(source, config["case_key"])
    client = carla.Client(host, port)
    client.set_timeout(20.0)
    saved_world = snapshot(client)
    world = client.get_world()
    settings = world.get_settings()
    if not settings.synchronous_mode or abs(settings.fixed_delta_seconds - .05) > 1e-6:
        raise ValueError("Dedicated Native world must be synchronous at 20 Hz")
    map_digest = hashlib.sha256(world.get_map().to_opendrive().encode()).hexdigest()
    if map_digest != site["map_sha256"]:
        raise ValueError("Native OpenDRIVE bytes differ from reviewed site map")
    attempt = Path(output_dir)
    output = attempt / "capture"
    output.mkdir()
    cameras = None
    failure = None
    try:
        cameras = OriginalCameras(world, carla, site, config)
        result = capture(world, source, config["case_key"], output, cameras.read)
        from encode_original import encode
        encoded = encode(attempt, config["case_key"], site["map_sha256"])
    except BaseException as error:
        failure = error
        raise
    finally:
        try:
            if cameras is not None:
                cameras.close()
        finally:
            restoration = restore(client, saved_world)
            if failure is not None:
                (attempt / "native-run-status.json").write_text(json.dumps({
                    "errors": [type(failure).__name__ + ": " + str(failure)],
                    "restoration": restoration, "physical_acceptance_claimed": False}, indent=2) + "\n")
    sealed = close(attempt, config["case_key"], site["map_sha256"], restoration)
    print(json.dumps({"case_id": result["case_id"], "original_frames": result["frame_count"],
                      "original_camera_images": 4 * result["frame_count"],
                      "encoded_views": sorted(encoded),
                      "capture_seal_format": sealed["format"],
                      "delivery_acceptance_claimed": False}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    if args.check:
        print(json.dumps({"exact_case_checked": check()["selected_case_id"], "simulation_started": False}))
        return
    if not args.output_dir:
        parser.error("--output-dir required for Native capture")
    native(args.output_dir, args.host, args.port)


if __name__ == "__main__":
    main()
