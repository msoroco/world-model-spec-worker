"""CPU preflight for a proposed Native scene and its retained review sources.

This checks byte identity and declared case joins. It cannot decide whether a
reviewer's public-highway or device finding is substantively correct.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import tempfile

from native_capture import REVIEW_SOURCES, reviewed_context
from opendrive_route_preflight import preflight as route_preflight
from runner import check_scene, resolve_reviewed_source


ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def preflight(scene_path, map_path, output):
    scene_path, map_path, output = map(Path, (scene_path, map_path, output))
    scene = check_scene(json.loads(scene_path.read_text()))
    if scene.get("diagnostic_only") is not False:
        raise ValueError("Native source preflight requires a nondiagnostic scene")
    packet_path = resolve_reviewed_source(scene, scene_path)
    packet = json.loads(packet_path.read_text())
    if packet.get("diagnostic_only") is not False:
        raise ValueError("Native source preflight requires a nondiagnostic packet")
    if sha(map_path) != scene["crossing"]["map_source_sha256"]:
        raise ValueError("proposed OpenDRIVE bytes differ from scene")
    route_binding = route_preflight(map_path, [scene_path])
    if output.exists():
        raise ValueError("use a fresh CPU preflight output directory")

    class Map:
        def to_opendrive(self):
            return map_path.read_bytes().decode("utf-8")

    class World:
        def get_map(self):
            return Map()

    output.parent.mkdir(parents=True, exist_ok=True)
    staged = Path(tempfile.mkdtemp(prefix="reviewed-preflight-", dir=output.parent))
    try:
        reviewed_context({**scene, "reviewed_context_source": str(packet_path)},
                         staged, World())
        receipt = {"format": "worker-reviewed-packet-cpu-preflight",
                   "case_id": scene["case_id"], "passed": True,
                   "source_packet_sha256": sha(packet_path),
                   "map_sha256": sha(map_path),
                   "route_binding": route_binding["cases"][scene["case_id"]],
                   "route_preflight_map_sha256": route_binding["map_sha256"],
                   "retained_source_hashes": {key: sha(staged / name)
                                              for key, name in REVIEW_SOURCES.items()},
                   "native_started": False, "physical_acceptance_claimed": False,
                   "legal_acceptance_claimed": False}
        (staged / "preflight.json").write_text(json.dumps(receipt, indent=2) + "\n")
        if output.exists():
            raise ValueError("use a fresh CPU preflight output directory")
        staged.rename(output)
        return receipt
    finally:
        if staged.exists():
            shutil.rmtree(staged)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scene", required=True)
    parser.add_argument("--map", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output).resolve()
    workspace = ROOT / ".runtime-work"
    if workspace not in output.parents:
        parser.error("output must be beneath .runtime-work")
    print(json.dumps(preflight(args.scene, args.map, output)))


if __name__ == "__main__":
    main()
