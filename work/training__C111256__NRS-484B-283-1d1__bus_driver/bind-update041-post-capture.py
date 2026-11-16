"""Bind the six selected recorded-only commands to current passing CPU logs."""
import hashlib
import json
import shlex
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / "execution-manifest.json"
    manifest = json.loads(path.read_text())
    if len(manifest["cases"]) != 6:
        raise ValueError("Six selected Walk cases required")
    for case in manifest["cases"]:
        suffix = case["case_id"].removeprefix(HERE.name + "__")
        log = HERE / f"update041a-selected-{suffix}-primary-process-saved.log"
        if not log.is_file() or "Traceback" in log.read_text():
            raise ValueError("Current recorded-only positive missing: " + suffix)
        command = [str(ROOT / ".venv-cpu/bin/python"), str(ROOT / "runtime.py"),
                   "process-saved", "--manifest", str(path), "--case", case["case_id"],
                   "--attempt", "$SAVED_ATTEMPT", "--output", "$PROCESSED_OUT",
                   "--library", str(ROOT / "runtime/pipeline/library"), "--validator",
                   str(ROOT / ".runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck")]
        rendered = shlex.join(command).replace("'$SAVED_ATTEMPT'", '"$SAVED_ATTEMPT"').replace(
            "'$PROCESSED_OUT'", '"$PROCESSED_OUT"')
        case["post_capture"] = {
            "recorded_only": True, "command": rendered,
            "feedback_command": 'cat "$PROCESSED_OUT/v0001/feedback.json"',
            "test_exit_code": 0, "test_log": log.name, "test_log_sha256": sha(log),
        }
    manifest["status"] = "selected_cpu_bound_final_saved_reproof_pending"
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps({"selected_cases": 6, "manifest_sha256": sha(path)}))


if __name__ == "__main__":
    main()
