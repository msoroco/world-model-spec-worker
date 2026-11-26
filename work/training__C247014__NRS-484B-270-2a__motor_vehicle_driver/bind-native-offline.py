"""Bind four exact pinned offline receipts into the selected Native draft."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "selected-native-draft-manifest.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        log = HERE / "native" / (suffix + "-offline.log")
        receipt = json.loads(log.read_text())
        if (receipt.get("case_id") != entry["case_id"] or
                receipt.get("candidate_id") != "primary" or
                receipt.get("offline_passed") is not True or
                receipt.get("simulation_started") is not False):
            raise ValueError("Offline receipt does not bind exact draft")
        entry["offline"] = {
            "command": ".venv-cpu/bin/python -B runtime.py offline --manifest work/" +
                       HERE.name + "/selected-native-draft-manifest.json --case " +
                       entry["case_id"] + " --output .runtime-work/c247014-offline-v7-" +
                       suffix + " --python $PWD/.venv-cpu/bin/python",
            "construction_sha256": entry["construction_sha256"],
            "exit_code": 0, "log": "native/" + log.name,
            "log_sha256": sha(log)}
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"bound": len(manifest["cases"]),
                      "manifest_sha256": sha(MANIFEST)}, sort_keys=True))


if __name__ == "__main__":
    main()
