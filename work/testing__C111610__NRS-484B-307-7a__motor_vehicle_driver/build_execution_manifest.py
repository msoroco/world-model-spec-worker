"""Bind five selected arrow constructions to explicit CPU fixture recipes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    draft = json.loads((ROOT / "execution-manifest.draft.json").read_text())
    entries = []
    for row in draft["cases"]:
        suffix = row["case_id"].removeprefix(ROOT.name + "__")
        if row["case_id"] != ROOT.name + "__" + suffix:
            raise ValueError("foreign selected arrow case")
        construction = ROOT / row["construction"]
        if sha(construction) != row["construction_sha256"]:
            raise ValueError("selected arrow construction changed")
        recipe = ROOT / ("diagnostic-" + suffix + "-recipe.json")
        if not recipe.is_file():
            raise ValueError("selected arrow CPU fixture recipe missing")
        entry = dict(row)
        entry.update(kind="delivery",
                     fixture_recipe=str(recipe.relative_to(REPO)),
                     native_handoff={"python_env_var": "CARLA_PYTHON",
                                     "host_env_var": "CARLA_HOST",
                                     "port_env_var": "CARLA_PORT",
                                     "site_root_env_var": "C111610_SITE_ROOT"})
        entries.append(entry)
    manifest = {"format": "worker-execution-manifest",
                "assignment_id": ROOT.name,
                "runtime_manifest_sha256": sha(REPO / "runtime/SOURCE-MANIFEST.json"),
                "cases": entries}
    (ROOT / "execution-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return len(entries)


if __name__ == "__main__":
    print("bound", build(), "selected arrow CPU fixtures")
