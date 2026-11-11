"""Bind current exact offline, compatibility and saved test logs for 499/501 ft."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / "execution-manifest.json"
    manifest = json.loads(path.read_text())
    for entry in manifest["cases"]:
        if not entry["case_id"].endswith(("__traveling_follow_499ft", "__traveling_follow_501ft")):
            continue
        target = 499 if entry["case_id"].endswith("499ft") else 501
        folder = HERE / "cases" / f"traveling_follow_{target}ft"
        for candidate_id, row in [("primary", entry),
                                  *[(item["id"], item) for item in entry["candidates"]]]:
            log = folder / (candidate_id + "-offline.log")
            if log.is_file():
                row["offline"] = {
                    "command": ".venv-cpu/bin/python runtime.py offline --manifest work/" + HERE.name + "/execution-manifest.json --case " + entry["case_id"] + " --candidate " + candidate_id + " --output .runtime-work/FRESH --python $PWD/.venv-cpu/bin/python",
                    "exit_code": 0,
                    "log": log.relative_to(HERE).as_posix(),
                    "log_sha256": digest(log),
                    "construction_sha256": row["construction_sha256"],
                }
            receipt = folder / (candidate_id + "-compatibility.json")
            if receipt.is_file():
                row["compatibility"] = {
                    "receipt": receipt.relative_to(HERE).as_posix(),
                    "sha256": digest(receipt),
                    "log": (folder / ("compat-" + candidate_id + ".log")).relative_to(HERE).as_posix(),
                    "negative_log": (folder / ("negative-" + candidate_id + ".log")).relative_to(HERE).as_posix(),
                }
                if candidate_id == "primary":
                    entry["negative"] = {"log": row["compatibility"]["negative_log"]}
        test_log = HERE / "cpu-tests.log"
        if test_log.is_file():
            entry["post_capture"] = {
                "recorded_only": True,
                "command": ".venv-cpu/bin/python runtime.py process-saved --manifest work/" + HERE.name + "/execution-manifest.json --case " + entry["case_id"] + " --attempt $ATTEMPT --output $OUTPUT --library runtime/library --validator $VALIDATOR",
                "feedback_command": "cat $OUTPUT/v0001/feedback.json",
                "test_log": test_log.name, "test_log_sha256": digest(test_log),
                "test_exit_code": 0,
            }
    path.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
