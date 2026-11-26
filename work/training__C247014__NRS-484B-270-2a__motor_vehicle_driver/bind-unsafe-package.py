"""Bind the fifth source-proved branch into the root execution handoff."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
SUFFIX = "exception_unsafe_available"
CASE = HERE.name + "__" + SUFFIX


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    selected = json.loads((HERE / "selected-native-draft-manifest.json").read_text())
    execution_path = HERE / "execution-manifest.json"
    execution = json.loads(execution_path.read_text())
    source = next(e for e in selected["cases"] if e["case_id"] == CASE)
    target = next(e for e in execution["cases"] if e["case_id"] == CASE)
    delivery = target.get("delivery_acceptance")
    if not delivery or delivery["test_exit_code"] != 0:
        raise ValueError("Fifth independent delivery audit must pass first")
    proof = HERE / "selected-native-draft" / SUFFIX / "saved-proof"
    saved_log = proof / "saved.log"
    if not saved_log.is_file() or not (proof / "processing.json").is_file():
        raise ValueError("Fifth saved-only proof missing")
    target.clear()
    target.update(source)
    target["delivery_acceptance"] = delivery
    target["post_capture"] = {
        "recorded_only": True,
        "command": ".venv-cpu/bin/python runtime.py process-saved --manifest work/" + HERE.name +
                   "/execution-manifest.json --case " + CASE +
                   " --attempt \"$SAVED_ATTEMPT\" --output \"$PROCESSED_OUT\"" +
                   " --library runtime/library --validator \"$VALIDATOR\"",
        "feedback_command": "cat \"$PROCESSED_OUT/v0001/feedback.json\"",
        "proof": str((proof / "processing.json").relative_to(HERE)),
        "test_exit_code": 0,
        "test_log": str(saved_log.relative_to(HERE)),
        "test_log_sha256": sha(saved_log),
    }
    write(execution_path, execution)

    # The root bundle is the witness_1 entrypoint, but its supported-case list
    # and shared runner must describe the full exact assignment inventory.
    fifth = json.loads((HERE / source["construction"]).read_text())
    first = json.loads((HERE / "selected-native-draft" / "witness_1" / "construction.json").read_text())
    for name in ("runner.py", "scene.py", "tests/test_scene.py"):
        content = next(f["content"] for f in fifth["files"] if f["path"] == name)
        path = HERE / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        next(f for f in first["files"] if f["path"] == name)["content"] = content
    config = json.loads((HERE / "config.json").read_text())
    config["supported_case_ids"] = [e["case_id"] for e in execution["cases"]]
    config_text = json.dumps(config, indent=2) + "\n"
    (HERE / "config.json").write_text(config_text)
    next(f for f in first["files"] if f["path"] == "config.json")["content"] = config_text
    write(HERE / "construction.json", first)
    print(json.dumps({"case_id": CASE, "manifest_sha256": sha(execution_path),
                      "root_construction_sha256": sha(HERE / "construction.json")}, sort_keys=True))


if __name__ == "__main__":
    main()
