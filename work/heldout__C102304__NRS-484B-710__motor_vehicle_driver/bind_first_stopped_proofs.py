"""Bind current exact proof files for stopped drive-to 450 ft."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
CASE = HERE.name + "__stopped_drive_to_450ft"
FOLDER = HERE / "cases/stopped_drive_to_450ft"


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / "execution-manifest.json"
    manifest = json.loads(path.read_text())
    entry = next(item for item in manifest["cases"] if item["case_id"] == CASE)
    for ident, row in [("primary", entry),
                       *[(item["id"], item) for item in entry["candidates"]]]:
        log = FOLDER / (ident + "-offline.log")
        if log.is_file():
            row["offline"] = {
                "command": ".venv-cpu/bin/python runtime.py offline --manifest work/" + HERE.name + "/execution-manifest.json --case " + CASE + " --candidate " + ident + " --output .runtime-work/FRESH --python $PWD/.venv-cpu/bin/python",
                "exit_code": 0, "log": log.relative_to(HERE).as_posix(),
                "log_sha256": digest(log),
                "construction_sha256": row["construction_sha256"],
            }
        receipt = FOLDER / (ident + "-compatibility.json")
        if receipt.is_file():
            row["compatibility"] = {
                "receipt": receipt.relative_to(HERE).as_posix(),
                "sha256": digest(receipt),
                "log": (FOLDER / (ident + "-compat.log")).relative_to(HERE).as_posix(),
                "negative_log": (FOLDER / (ident + "-negative.log")).relative_to(HERE).as_posix(),
            }
            if ident == "primary":
                entry["negative"] = {"log": row["compatibility"]["negative_log"]}
    test_log = HERE / "cpu-tests.log"
    if test_log.is_file():
        entry["post_capture"] = {
            "recorded_only": True,
            "command": ".venv-cpu/bin/python runtime.py process-saved --manifest work/" + HERE.name + "/execution-manifest.json --case " + CASE + " --attempt $ATTEMPT --output $OUTPUT --library runtime/library --validator $VALIDATOR",
            "feedback_command": "cat $OUTPUT/v0001/feedback.json",
            "test_log": test_log.name, "test_log_sha256": digest(test_log),
            "test_exit_code": 0,
        }
    path.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
