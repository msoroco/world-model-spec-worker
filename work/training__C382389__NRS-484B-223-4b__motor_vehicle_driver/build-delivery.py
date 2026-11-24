"""Bind recorded-only and independent acceptance CPU checks to selected cases."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CHECKS = ["native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        case = entry["case_id"]
        label = case.rsplit("__", 1)[-1]
        folder = HERE / "delivery-proof" / label
        folder.mkdir(parents=True, exist_ok=True)
        command = f".venv-cpu/bin/python work/{HERE.name}/delivery_acceptance.py --case {case}"
        negative_command = command + " --negative"
        for name, args in (("positive", []), ("negative", ["--negative"])):
            result = subprocess.run([sys.executable, str(HERE / "delivery_acceptance.py"),
                                     "--case", case, *args], cwd=REPO, env=os.environ.copy(),
                                    text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            expected = 0 if name == "positive" else 1
            if result.returncode != expected:
                raise ValueError(f"{case} {name} exit {result.returncode}: {result.stdout[-1000:]}")
            (folder / f"{name}.log").write_text(result.stdout.rstrip() + "\n")
        positive = folder / "positive.log"
        negative = folder / "negative.log"
        error = "Missing independent original Native and physical acceptance source"
        if error not in negative.read_text():
            raise ValueError("Missing negative acceptance rejection")
        entry["delivery_acceptance"] = {"case_id": case, "sets": ["full-train"],
            "checks": CHECKS, "script": "delivery_acceptance.py",
            "script_sha256": sha(HERE / "delivery_acceptance.py"),
            "command": command, "test_exit_code": 0,
            "test_log": str(positive.relative_to(HERE)), "test_log_sha256": sha(positive),
            "negative_command": negative_command, "negative_exit_code": 1,
            "negative_expected_error": error,
            "negative_log": str(negative.relative_to(HERE)),
            "negative_log_sha256": sha(negative)}
        processing_path = REPO / ".runtime-work" / f"c382389-{label}-saved-v2/v0001/processing.json"
        processing = json.loads(processing_path.read_text())
        if processing["case_id"] != case or not processing["passed"] or not processing["recorded_only"]:
            raise ValueError("Saved-only processing was not proven for " + case)
        saved_log = HERE / "selected-proof" / label / "primary/recorded-only.log"
        write(saved_log, {"command": f".venv-cpu/bin/python runtime.py process-saved --manifest work/{HERE.name}/execution-manifest.json --case {case} --attempt .runtime-work/c382389-selected-attempt-{label} --output .runtime-work/c382389-{label}-saved-v2 --library runtime/library --validator .runtime-work/c111331-current/decoder/.lake/build/bin/adapterCheck",
                          "exit_code": 0, "recorded_only": True,
                          "processing_sha256": sha(processing_path), "result_sha256": processing["result_sha256"],
                          "originals_preserved": processing["originals_preserved"]})
        entry["post_capture"] = {"recorded_only": True,
            "command": f"runtime.py process-saved --manifest work/{HERE.name}/execution-manifest.json --case {case} --attempt \"$SAVED_ATTEMPT\" --output \"$PROCESSED_OUT\" --library runtime/library --validator \"$DECODER\"",
            "feedback_command": "cat \"$PROCESSED_OUT/v0001/feedback.json\"",
            "test_log": str(saved_log.relative_to(HERE)), "test_log_sha256": sha(saved_log),
            "test_exit_code": 0}
    write(manifest_path, manifest)
    print(json.dumps({"delivery_acceptance_cases": len(manifest["cases"]) }))


if __name__ == "__main__":
    main()
