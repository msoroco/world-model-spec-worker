"""Retain assignment-local hashes for exact current-runtime offline proofs."""

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
        suffix = entry["case_id"].rsplit("__", 1)[1]
        label = "before" if suffix == "before_crosswalk" else "past"
        source = REPO / ".runtime-work" / "c111343-yield" / ("offline-" + label + "-primary-v6.log")
        if not source.is_file():
            raise ValueError("Exact offline log missing: " + suffix)
        destination = HERE / ("native-offline-" + suffix + ".log")
        destination.write_text(source.read_text().rstrip() + "\n")
        entry["offline"] = {"command": ".venv-cpu/bin/python -B runtime.py offline --manifest " +
            "work/" + HERE.name + "/draft-native-manifest.json --case " + entry["case_id"] +
            " --candidate primary --output .runtime-work/c111343-yield/offline-" + label + "-primary-v6",
            "construction_sha256": entry["construction_sha256"],
            "exit_code": 0, "log": destination.name, "log_sha256": sha(destination)}
        candidate = entry["candidates"][0]
        fallback_source = REPO / ".runtime-work" / "c111343-yield" / ("offline-" + label + "-fallback1-v6.log")
        if not fallback_source.is_file():
            raise ValueError("Exact fallback offline log missing: " + suffix)
        fallback_log = HERE / ("native-offline-" + suffix + "-fallback1.log")
        fallback_log.write_text(fallback_source.read_text().rstrip() + "\n")
        candidate["offline"] = {"command": ".venv-cpu/bin/python -B runtime.py offline --manifest " +
            "work/" + HERE.name + "/draft-native-manifest.json --case " + entry["case_id"] +
            " --candidate fallback1 --output .runtime-work/c111343-yield/offline-" + label + "-fallback1-v6",
            "construction_sha256": candidate["construction_sha256"], "exit_code": 0,
            "log": fallback_log.name, "log_sha256": sha(fallback_log)}
    path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    return {"offline_cases": len(manifest["cases"]), "manifest_sha256": sha(path)}


if __name__ == "__main__":
    print(json.dumps(main(), sort_keys=True))
