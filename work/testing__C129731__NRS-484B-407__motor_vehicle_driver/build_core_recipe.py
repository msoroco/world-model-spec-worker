"""Bind diagnostic Core/video specs and sight packets without returning media."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
NAMES = ("overview", "approach", "reference_corner", "driver_reference")
SOURCES = ("frame_map.json", "ego_motion.json", "sight_rays.json",
           "road_geometry.json", "approach_motion.json")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(generated: Path) -> None:
    generated = generated.resolve()
    if not generated.is_relative_to(REPO / ".runtime-work"):
        raise ValueError("Generated camera media must stay under .runtime-work")
    camera_hashes = {name: sha(generated / (name + ".mkv")) for name in NAMES}
    for suffix in ("distance_reference", "distance_below_500ft",
                   "distance_at_500ft", "distance_above_500ft"):
        folder = HERE / "fixtures" / suffix
        inventory = json.loads((folder / "inventory.json").read_text())
        inventory["camera_sources"] = {
            name: {"path": name + ".mkv", "source_kind": "original_native",
                   "sha256": camera_hashes[name]}
            for name in NAMES}
        inventory["diagnostic_fixture"] = True
        inventory_path = folder / "core-inventory.json"
        inventory_path.write_text(json.dumps(inventory, indent=2) + "\n")
        spec = folder / "core-diagnostic.draft.json"
        from_spec = json.loads(spec.read_text())
        if {video["path"] for video in from_spec["videos"]} != {
                name + ".mkv" for name in NAMES}:
            raise ValueError("Diagnostic four-view profile changed")
        sources = []
        for name in SOURCES:
            path = folder / name
            if not path.is_file():
                if name == "approach_motion.json" and suffix == "distance_reference":
                    continue
                raise ValueError("Missing diagnostic sight packet: " + name)
            sources.append({"path": name,
                            "source": str(path.relative_to(REPO)),
                            "sha256": sha(path)})
        sources.append({"path": "inventory.json",
                        "source": str(inventory_path.relative_to(REPO)),
                        "sha256": sha(inventory_path)})
        recipe = {"format": "worker-fixture-recipe", "sources": sources,
                  "generator": {"source": str(spec.relative_to(REPO)),
                                "sha256": sha(spec)},
                  "scope": "900-frame Core/video diagnostic wiring only; not original physical evidence"}
        (folder / "core-fixture-recipe.json").write_text(
            json.dumps(recipe, indent=2) + "\n")
        print(suffix, sha(folder / "core-fixture-recipe.json"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--generated", type=Path, required=True)
    build(parser.parse_args().generated)
