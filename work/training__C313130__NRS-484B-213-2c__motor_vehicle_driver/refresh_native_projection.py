"""Rebind original Native capture source in eight exact constructions."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False,
                               allow_nan=False) + "\n")


def update_construction(path, source):
    data = json.loads(path.read_text())
    matches = [entry for entry in data["files"] if entry["path"] == source]
    if len(matches) != 1:
        raise ValueError("Exact Native source missing: " + path.name)
    matches[0]["content"] = (HERE / source).read_text()
    write(path, data)


def update_manifest(path):
    manifest = json.loads(path.read_text())
    for entry in manifest["cases"]:
        for selected in (entry, *entry["candidates"]):
            construction = HERE / selected["construction"]
            source = "one_way_capture.py" if "one_way" in entry["case_id"] else "native_capture.py"
            update_construction(construction, source)
            selected["construction_sha256"] = digest(construction)
            if "offline" in selected:
                selected["offline"]["construction_sha256"] = digest(construction)
    write(path, manifest)


def main():
    update_construction(HERE / "construction.json", "native_capture.py")
    for name in ("selected-probe-manifest.json", "one-way-probe-manifest.json",
                 "execution-manifest.json"):
        update_manifest(HERE / name)
    print(json.dumps({"constructions": 8,
                      "execution_manifest_sha256": digest(HERE / "execution-manifest.json")}))


if __name__ == "__main__":
    main()
