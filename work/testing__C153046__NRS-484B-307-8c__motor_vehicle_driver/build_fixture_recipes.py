"""Inventory source-bound, text-generated CPU diagnostics for all exact cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile

from build_case_plan import KINDS
from tests.test_saved_finalizer import attempt

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CAMERAS = (("overview", 1920, 1080, "red"),
           ("approach", 1280, 720, "green"),
           ("reference_corner", 1280, 720, "blue"),
           ("driver_reference", 1280, 720, "white"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> None:
    private = REPO / ".runtime-work" / "c153046-fixture-source-build"
    private.mkdir(parents=True, exist_ok=True)
    for suffix in KINDS:
        folder = ROOT / "diagnostics" / suffix
        folder.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=private) as temporary:
            fixture = Path(temporary)
            case_id = attempt(fixture, suffix=suffix)
            generated = {path.name: path.read_text(encoding="utf-8")
                         for path in sorted(fixture.iterdir())
                         if path.suffix in (".txt", ".json", ".jsonl") and
                         path.name != "config.json"}
        note_path = folder / "diagnostic-source-note.json"
        note_path.write_text(json.dumps({
            "case_id": case_id,
            "kind": "synthetic_cpu_protocol",
            "original_native_acquisition": False,
            "physical_acceptance_claimed": False,
        }, indent=2) + "\n")
        specification = {
            "files": generated,
            "graphs": [],
            "videos": [{"path": name + ".mkv", "frames": 13,
                        "width": width, "height": height, "fps": 20, "color": color}
                       for name, width, height, color in CAMERAS],
        }
        spec_path = folder / "diagnostic.json"
        spec_path.write_text(json.dumps(specification, indent=2) + "\n")
        recipe = {"format": "worker-fixture-recipe",
                  "sources": [{"path": note_path.name,
                               "source": str(note_path.relative_to(REPO)),
                               "sha256": sha(note_path)}],
                  "generator": {"source": str(spec_path.relative_to(REPO)),
                                "sha256": sha(spec_path)}}
        (folder / "fixture-recipe.json").write_text(json.dumps(recipe, indent=2) + "\n")
        print("inventoried diagnostic source recipe", suffix)


if __name__ == "__main__":
    build()
