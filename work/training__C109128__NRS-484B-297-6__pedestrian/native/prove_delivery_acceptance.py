"""Run exact positive and missing-source negative CPU delivery audit fixtures."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
REPO = FOLDER.parents[1]
SCRATCH = REPO / ".runtime-work/c109128/delivery-audit"
SCRIPT = FOLDER / "delivery_audit.py"
CHECKS = ["native_source", "all_participants", "time_join", "full_video_decode",
          "actual_pixels", "physical_completion", "full_sidewalk_return",
          "obstruction_and_adjacent_highway_review"]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def main():
    SCRATCH.mkdir(parents=True, exist_ok=True)
    manifest = read(FOLDER / "execution-manifest.json")
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.rsplit("__", 1)[-1]
        attempt = (REPO / ".runtime-work/c109128/selected-compat-refresh" / (suffix + "-primary")
                   if suffix.startswith("condition_") else
                   REPO / ".runtime-work/c109128/alt-compat-current" / (suffix + "-primary"))
        receipt = FOLDER / ("process-saved-refresh-" + suffix + ".json" if
                            suffix.startswith("condition_") else
                            "process-saved-" + suffix + ".json")
        base = [sys.executable, str(SCRIPT), "--case", case, "--candidate", "primary",
                "--attempt", str(attempt), "--processing", str(receipt),
                "--diagnostic"]
        positive_output = SCRATCH / (suffix + "-positive-proof.json")
        if positive_output.exists():
            positive_output.unlink()
        positive = base + ["--output", str(positive_output)]
        positive_log = FOLDER / ("delivery-" + suffix + "-positive.log")
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        with positive_log.open("w") as stream:
            good = subprocess.run(positive, cwd=REPO, env=env,
                                  stdout=stream, stderr=subprocess.STDOUT)
        if good.returncode != 0 or not read(positive_output)["diagnostic_only"]:
            raise ValueError("Positive diagnostic delivery audit failed: " + suffix)
        negative = base + ["--output", str(SCRATCH / (suffix + "-negative-proof.json")),
                           "--omit-source", "sidewalk_context.json"]
        negative_log = FOLDER / ("delivery-" + suffix + "-negative.log")
        with negative_log.open("w") as stream:
            bad = subprocess.run(negative, cwd=REPO, env=env,
                                 stdout=stream, stderr=subprocess.STDOUT)
        expected = "Missing source: sidewalk_context.json"
        if bad.returncode == 0 or expected not in negative_log.read_text():
            raise ValueError("Missing-source diagnostic delivery audit accepted: " + suffix)
        entry["delivery_acceptance"] = {
            "case_id": case, "sets": ["full-train"], "checks": CHECKS,
            "script": SCRIPT.name, "script_sha256": sha(SCRIPT),
            "command": " ".join(positive), "test_exit_code": 0,
            "test_log": positive_log.name, "test_log_sha256": sha(positive_log),
            "negative_command": " ".join(negative),
            "negative_exit_code": bad.returncode,
            "negative_expected_error": expected,
            "negative_log": negative_log.name,
            "negative_log_sha256": sha(negative_log)}
    (FOLDER / "execution-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"cases": len(manifest["cases"]),
                      "manifest_sha256": sha(FOLDER / "execution-manifest.json")}))


if __name__ == "__main__":
    main()
