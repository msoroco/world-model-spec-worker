"""Bind six exact current-runtime offline construction logs."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    path = HERE / "draft-native-manifest.json"
    manifest = json.loads(path.read_text())
    for entry in manifest["cases"]:
        slug = entry["case_id"].rsplit("__", 1)[1]
        label = "condition-a" if slug == "condition_a" else slug
        version = "v10" if slug == "extended_park_no_transfer" else "v9"
        source = REPO / ".runtime-work" / "c149498-loading" / ("offline-" + label + "-" + version) / "offline.log"
        if not source.is_file():
            raise ValueError("Exact offline log missing: " + slug)
        destination = HERE / ("native-proof-" + slug + ".log")
        destination.write_text(source.read_text().rstrip() + "\n")
        entry["offline"] = {"command": ".venv-cpu/bin/python -B runtime.py offline --manifest " +
            "work/" + HERE.name + "/draft-native-manifest.json --case " + entry["case_id"] +
            " --output .runtime-work/c149498-loading/offline-" + label + "-" + version,
            "construction_sha256": entry["construction_sha256"],
            "exit_code": 0, "log": destination.name, "log_sha256": sha(destination)}
    path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    return {"offline_cases": len(manifest["cases"]), "manifest_sha256": sha(path)}


if __name__ == "__main__":
    print(json.dumps(main(), sort_keys=True))
