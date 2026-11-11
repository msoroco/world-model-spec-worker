"""Bind each selected fallback to its own exact raw diagnostic recipe."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
BASE = json.loads((ROOT / "execution-manifest.json").read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    rows = []
    for case in ("reference", "contrast", "divided_reference", "divided_opening"):
        for candidate in ("fallback1", "fallback2", "fallback3"):
            recipe = ROOT / f"update015-selected-{case}-{candidate}-recipe.json"
            value = json.loads(json.dumps(BASE))
            value["diagnostic_case"] = ROOT.name + "__" + case
            value["diagnostic_candidate"] = candidate
            entry = next(row for row in value["cases"] if row["case_id"] == value["diagnostic_case"])
            entry["fixture_recipe"] = recipe.relative_to(REPO).as_posix()
            target = ROOT / f"execution-manifest-{case}-{candidate}.json"
            target.write_text(json.dumps(value, indent=2) + "\n")
            rows.append({"case": case, "candidate": candidate,
                         "manifest": target.name, "manifest_sha256": sha(target),
                         "recipe_sha256": sha(recipe)})
    target = ROOT / "update015-selected-candidate-manifests.json"
    target.write_text(json.dumps({"format": "c111662-selected-candidate-manifests-v1",
                                  "base_manifest_sha256": sha(ROOT / "execution-manifest.json"),
                                  "variants": rows}, indent=2) + "\n")
    print(json.dumps({"fallback_variants": len(rows), "matrix_sha256": sha(target)}))


if __name__ == "__main__":
    build()
