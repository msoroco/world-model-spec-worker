"""Exact crossing runner with original site review supplied at Native launch.

The packaged engineering scene can be checked on CPU. Native capture requires a
separately reviewed packet and its hash, and refuses the synthetic CPU packet.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

from crossing_control import validate_routes


def check_scene(scene):
    validate_routes(scene)
    if scene.get("capture_rate_hz") != 20 or not isinstance(scene.get("duration_s"), (int, float)):
        raise ValueError("20 Hz positive duration is required")
    if scene["duration_s"] <= 0 or round(scene["duration_s"] * 20) < 2:
        raise ValueError("Native capture needs at least two original frames")
    if type(scene.get("other_entered_first")) is not bool:
        raise ValueError("entry-order target must be explicit")
    if scene.get("ego_response_request", "yield") not in ("yield", "advance"):
        raise ValueError("ego response request must be yield or advance")
    if not scene.get("case_id") or scene.get("diagnostic_only") is not False:
        raise ValueError("selected source-gated scene identity or scope differs")
    return scene


def reviewed_source(scene, path_string, expected_sha):
    if not path_string or not expected_sha:
        raise ValueError("source-hashed reviewed crossing packet required")
    raw = Path(path_string)
    path = raw.resolve()
    if not path.is_file() or raw.is_symlink():
        raise ValueError("reviewed crossing packet missing or symlinked")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != expected_sha:
        raise ValueError("reviewed crossing packet hash differs")
    packet = json.loads(path.read_text(encoding="utf-8"))
    if packet.get("diagnostic_only") is not False:
        raise ValueError("synthetic diagnostic packet cannot authorize Native capture")
    if packet.get("crossing") != scene["crossing"] or packet.get("case_id") != scene["case_id"]:
        raise ValueError("reviewed crossing or case differs from selected scene")
    return path, digest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", default=str(Path(__file__).with_name("scene.json")))
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--output-dir")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=2000)
    args = parser.parse_args()
    scene = check_scene(json.loads(Path(args.scene).read_text(encoding="utf-8")))
    from case_builder import config
    expected = config(scene)
    actual = json.loads(Path(args.scene).with_name("config.json").read_text(encoding="utf-8"))
    if any(actual.get(key) != value for key, value in expected.items()):
        raise ValueError("materialized exact config differs from selected scene")
    if args.check:
        print(json.dumps({"case_id": scene["case_id"],
                          "static_construction_valid": True, "native_started": False}))
        return
    if not args.output_dir:
        parser.error("use --check or --output-dir")
    source, digest = reviewed_source(
        scene, os.environ.get("SCENARIO_C125714_REVIEWED_PACKET"),
        os.environ.get("SCENARIO_C125714_REVIEWED_PACKET_SHA256"))
    scene = {**scene, "reviewed_context_source": str(source),
             "reviewed_context_sha256": digest}
    from native_capture import run_native
    run_native(scene, args.output_dir, args.host, args.port)


if __name__ == "__main__":
    main()
