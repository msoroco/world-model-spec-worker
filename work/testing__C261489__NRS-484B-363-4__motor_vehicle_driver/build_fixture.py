"""Build case-specific textual diagnostic sources atop the pinned generic Native scaffold."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE / "tests"))
from test_school_pass import rows, scene


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")


def main() -> None:
    base = json.loads((REPO / "runtime/fixtures/example.json").read_text())
    raw_trace = [json.loads(line) for line in base["files"]["trace.jsonl"].splitlines()]
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        name = case_id[len(HERE.name) + 2:]
        source_root = HERE / "cases" / name / "diagnostic-sources"
        site = scene(name)
        context = source_root / "context.json"
        write(context, site)
        original = rows(site)[:9]
        for source, recorded in zip(original, raw_trace):
            source["original_frame"] = recorded["frame"]
            source["time_s"] = recorded["time_s"]
        trace = source_root / "original-trace.jsonl"
        trace.write_text("\n".join(json.dumps(row, sort_keys=True) for row in original) + "\n")
        cameras = source_root / "cameras.json"
        write(cameras, {"assignment_id": HERE.name, "case_id": case_id,
                        "views": ["overview", "approach", "reference_corner", "driver_reference"],
                        "fps": 20, "frame_count": 9,
                        "scope": "synthetic diagnostic only; no original camera source"})
        receipt = source_root / "receipt.json"
        write(receipt, {"assignment_id": HERE.name, "case_id": case_id,
                        "source_kind": "synthetic_diagnostic_fixture", "diagnostic_fixture": True,
                        "fps": 20, "frame_count": 9,
                        "context_sha256": sha(context), "trace_sha256": sha(trace),
                        "camera_manifest_sha256": sha(cameras)})
        scaffold = json.loads(json.dumps(base))
        scaffold["files"]["fixture-provenance.json"] = json.dumps({
            "diagnostic_fixture": True, "frames": 9,
            "scope": "CPU diagnostic only; generic retained Native shapes and synthetic videos. School-pass source files are separate case-specific textual inputs; no physical claim.",
        }, sort_keys=True) + "\n"
        capture_meta = json.loads(scaffold["files"]["capture/manifest.json"])
        capture_meta["case_id"] = case_id
        scaffold["files"]["capture/manifest.json"] = json.dumps(capture_meta, indent=2) + "\n"
        scaffold_path = HERE / "cases" / name / "diagnostic-scaffold.json"
        write(scaffold_path, scaffold)
        recipe = {
            "format": "worker-fixture-recipe",
            "generator": {"source": str(scaffold_path.relative_to(REPO)), "sha256": sha(scaffold_path)},
            "sources": [{"path": path.name, "source": str(path.relative_to(REPO)),
                         "sha256": sha(path)} for path in (context, trace, cameras, receipt)],
        }
        recipe_path = HERE / "cases" / name / "fixture-recipe.json"
        write(recipe_path, recipe)
        entry["fixture_recipe"] = str(recipe_path.relative_to(REPO))
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(len(manifest["cases"]), "source-hashed case-specific textual diagnostic recipes")


if __name__ == "__main__":
    main()
