"""Update exact primary/fallback constructions with the worker-owned CARLA adapter."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.json"
OPERATOR = HERE / "native_operator.py"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    item = {"path": "native_operator.py", "content": OPERATOR.read_text(),
            "source": str(OPERATOR.relative_to(REPO))}
    for entry in manifest["cases"]:
        for selected in (entry, *entry["candidates"]):
            path = HERE / selected["construction"]
            construction = json.loads(path.read_text())
            construction["files"] = [row for row in construction["files"]
                                     if row["path"] != "native_operator.py"] + [item]
            path.write_text(json.dumps(construction, indent=2, sort_keys=True) + "\n")
            selected["construction_sha256"] = sha(path)
    (HERE / "construction.json").write_text((HERE / manifest["cases"][0]["construction"]).read_text())
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(len(manifest["cases"]), "primary and fallback Native operators embedded")


if __name__ == "__main__":
    main()
