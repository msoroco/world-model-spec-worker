"""Run and bind exact CPU proofs for the five added stopped cases."""
from __future__ import annotations

from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.json"
DECODER = ROOT / ".runtime-work/fire-decoder/.lake/build/bin/adapterCheck"
TARGETS = [("stopped_drive_to", 500), ("stopped_drive_to", 550),
           ("stopped_park", 450), ("stopped_park", 500), ("stopped_park", 550)]


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def run(args, destination):
    with destination.open("w") as stream:
        subprocess.run(args, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, check=True)


def main():
    manifest = json.loads(MANIFEST.read_text())
    targets = TARGETS[2:] if "--park-only" in sys.argv else TARGETS
    names = (["authorized_emergency_at500"] if "--exception" in sys.argv
             else [f"{branch}_{target}ft" for branch, target in targets])
    for name in names:
        case = f"{HERE.name}__{name}"
        folder = HERE / "cases" / name
        entry = next(item for item in manifest["cases"] if item["case_id"] == case)
        for ident, row in [("primary", entry),
                           *[(item["id"], item) for item in entry["candidates"]]]:
            work = ROOT / ".runtime-work" / f"proof-{name}-{ident}"
            if work.exists():
                shutil.rmtree(work)
            work.mkdir(parents=True, exist_ok=True)
            offline = work / "offline"
            compatibility = work / "compatibility"
            offline_log = folder / f"{ident}-offline.log"
            compat_log = folder / f"{ident}-compat.log"
            print(case, ident, flush=True)
            run([sys.executable, "runtime.py", "offline", "--manifest", str(MANIFEST),
                 "--case", case, "--candidate", ident, "--output", str(offline),
                 "--python", sys.executable], offline_log)
            run([sys.executable, "runtime.py", "compatibility", "--manifest", str(MANIFEST),
                 "--case", case, "--candidate", ident, "--output", str(compatibility),
                 "--library", "runtime/library", "--validator", str(DECODER)], work / "compatibility-command.log")
            receipt = folder / f"{ident}-compatibility.json"
            negative = folder / f"{ident}-negative.log"
            shutil.copyfile(compatibility / "compatibility.json", receipt)
            shutil.copyfile(compatibility / "compatibility-analysis.log", compat_log)
            shutil.copyfile(compatibility / "negative-analysis.log", negative)
            result = json.loads(receipt.read_text())
            if not result["passed"] or result["candidate_id"] != ident:
                raise ValueError(f"Compatibility failure: {case} {ident}")
            row["offline"] = {
                "command": f".venv-cpu/bin/python runtime.py offline --manifest work/{HERE.name}/execution-manifest.json --case {case} --candidate {ident} --output .runtime-work/FRESH --python $PWD/.venv-cpu/bin/python",
                "exit_code": 0, "log": offline_log.relative_to(HERE).as_posix(),
                "log_sha256": digest(offline_log),
                "construction_sha256": row["construction_sha256"]}
            row["compatibility"] = {
                "receipt": receipt.relative_to(HERE).as_posix(), "sha256": digest(receipt),
                "log": compat_log.relative_to(HERE).as_posix(),
                "negative_log": negative.relative_to(HERE).as_posix()}
            if ident == "primary":
                entry["negative"] = {"log": row["compatibility"]["negative_log"]}
            MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
