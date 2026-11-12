"""Source-hashed synthetic recipes for no-stop-object right-turn diagnostics."""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / "native"))
from variant_geometry import open_drive_for


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = HERE / "draft-absent-reference-execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    outputs = []
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(HERE.name + "__")
        source = "reference" if suffix == "absent_reference" else "contrast"
        baseline = json.loads((HERE / f"update015-{source}-diagnostic.json").read_text())
        files = baseline["files"]
        geometry = json.loads(files["road_geometry.json"])
        if geometry.get("synthetic_diagnostic") is not True:
            raise ValueError("Baseline geometry is not a diagnostic")
        geometry.update({"stop_line_y_m": None, "nearest_crosswalk_y_m": None,
                         "intersection_near_y_m": -7.0,
                         "stopping_reference_kind": "intersection_boundary",
                         "stopping_reference_y_m": -7.0,
                         "native_absence_observed": False})
        files["road_geometry.json"] = json.dumps(geometry) + "\n"
        files["context.json"] = json.dumps({"surveyed_right_turn": geometry}) + "\n"
        files["road.xodr"] = open_drive_for(suffix)
        capture = json.loads(files["capture/manifest.json"])
        capture["sources"]["road.xodr"] = hashlib.sha256(files["road.xodr"].encode()).hexdigest()
        files["capture/manifest.json"] = json.dumps(capture) + "\n"
        target = HERE / f"update024-{suffix}-diagnostic.json"
        target.write_text(json.dumps(baseline, separators=(",", ":"), allow_nan=False) + "\n")
        if target.stat().st_size >= 2 * 1024 * 1024:
            raise ValueError("Absent-reference diagnostic exceeds return limit")
        relative = target.relative_to(ROOT).as_posix()
        digest = sha(target)
        recipe = {"format": "worker-fixture-recipe",
                  "sources": [{"path": "diagnostic-input.json", "source": relative,
                               "sha256": digest}],
                  "generator": {"source": relative, "sha256": digest}}
        recipe_path = HERE / f"update024-{suffix}-recipe.json"
        recipe_path.write_text(json.dumps(recipe, indent=2) + "\n")
        entry["fixture_recipe"] = relative.replace("-diagnostic.json", "-recipe.json")
        outputs.append({"case_id": entry["case_id"], "diagnostic_sha256": digest,
                        "recipe_sha256": sha(recipe_path), "bytes": target.stat().st_size})
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    summary = {"format": "c110919-absent-reference-recipes-v1",
               "manifest_sha256": sha(manifest_path), "cases": outputs,
               "synthetic_diagnostic": True, "selected": False}
    path = HERE / "update024-absent-recipe-summary.json"
    path.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"cases": len(outputs), "manifest_sha256": sha(manifest_path),
                      "recipe_summary_sha256": sha(path)}))


if __name__ == "__main__":
    main()
