"""Run exact offline and positive/negative compatibility for exception probes."""

from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.json"


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def run(command, log):
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    log.write_text(completed.stdout + completed.stderr)
    if completed.returncode:
        raise ValueError("Proof failed: " + " ".join(command) + "\n" + log.read_text()[-1200:])


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].split("__")[-1]
        if suffix not in ("ordinary_police_at499", "authorized_offduty_at499",
                          "unauthorized_onduty_at499", "authorized_police_at499"):
            continue
        folder = HERE / "cases" / suffix
        for label, row in [("primary", entry), *[(c["id"], c) for c in entry["candidates"]]]:
            stem = "c109514-" + suffix + "-" + label + "-" + row["construction_sha256"][:12]
            attempt = 1
            while ((ROOT / ".runtime-work" / (stem + "-r" + str(attempt) + "-offline")).exists()
                   or (ROOT / ".runtime-work" / (stem + "-r" + str(attempt) + "-compat")).exists()):
                attempt += 1
            stem += "-r" + str(attempt)
            offline = [".venv-cpu/bin/python", "runtime.py", "offline", "--manifest",
                       MANIFEST.relative_to(ROOT).as_posix(), "--case", entry["case_id"],
                       "--candidate", label, "--output", ".runtime-work/" + stem + "-offline",
                       "--python", str(ROOT / ".venv-cpu/bin/python")]
            offline_log = folder / (label + "-offline.log")
            run(offline, offline_log)
            row["offline"] = {"command": " ".join(offline), "exit_code": 0,
                              "log": offline_log.relative_to(HERE).as_posix(),
                              "log_sha256": digest(offline_log),
                              "construction_sha256": row["construction_sha256"]}
            output = ROOT / ".runtime-work" / (stem + "-compat")
            compatibility = [".venv-cpu/bin/python", "runtime.py", "compatibility", "--manifest",
                             MANIFEST.relative_to(ROOT).as_posix(), "--case", entry["case_id"],
                             "--candidate", label, "--output", output.relative_to(ROOT).as_posix(),
                             "--library", "runtime/library", "--validator",
                             ".runtime-work/fire-decoder/.lake/build/bin/adapterCheck"]
            run(compatibility, folder / (label + "-compat-command.log"))
            receipt = folder / (label + "-compatibility.json")
            analysis = folder / (label + "-compat.log")
            negative = folder / (label + "-negative.log")
            shutil.copy2(output / "compatibility.json", receipt)
            shutil.copy2(output / "compatibility-analysis.log", analysis)
            shutil.copy2(output / "negative-analysis.log", negative)
            row["compatibility"] = {"receipt": receipt.relative_to(HERE).as_posix(),
                                    "sha256": digest(receipt),
                                    "log": analysis.relative_to(HERE).as_posix(),
                                    "negative_log": negative.relative_to(HERE).as_posix()}
            if label == "primary":
                entry["negative"] = {"log": negative.relative_to(HERE).as_posix()}
            MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
            print(suffix, label, "offline and positive/negative compatibility passed", flush=True)


if __name__ == "__main__":
    main()
