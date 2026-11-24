"""Run three physical outcome fixtures and lifecycle order for each selected case."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
KINDS = ("complete_motion", "incomplete_motion", "missing_evidence", "lifecycle")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    for entry, case in zip(manifest["cases"], ("condition_a", "condition_b")):
        folder = HERE / "selected-physical" / case
        folder.mkdir(parents=True, exist_ok=True)
        proof = {"format": "c110763-selected-physical-cpu-v1", "case_id": entry["case_id"],
                 "construction_sha256": entry["construction_sha256"],
                 "runtime_manifest_sha256": manifest["runtime_manifest_sha256"],
                 "script_sha256": sha(HERE / "prove-selected-physical.py"), "fixtures": [],
                 "scope": "synthetic Native-shaped motion and lifecycle only; original motion, pixels and legal acceptance unverified"}
        for kind in KINDS:
            result = folder / f"{kind}.json"
            log = folder / f"{kind}.log"
            command = [sys.executable, str(HERE / "prove-selected-physical.py"),
                       "--case", case, "--kind", kind, "--output", str(result)]
            with log.open("w") as stream:
                code = subprocess.run(command, cwd=ROOT, stdout=stream,
                                      stderr=subprocess.STDOUT).returncode
            if code:
                raise RuntimeError(f"{case} {kind} failed; see {log}")
            row = {"command": f".venv-cpu/bin/python work/{HERE.name}/prove-selected-physical.py --case {case} --kind {kind} --output work/{HERE.name}/selected-physical/{case}/{kind}.json",
                   "exit_code": 0, "log": f"selected-physical/{case}/{kind}.log",
                   "log_sha256": sha(log), "result": f"selected-physical/{case}/{kind}.json",
                   "result_sha256": sha(result)}
            if kind == "lifecycle":
                row["events"] = json.loads(result.read_text())["events"]
                proof["lifecycle"] = row
            else:
                row["kind"] = kind
                proof["fixtures"].append(row)
        (folder / "proof.json").write_text(json.dumps(proof, indent=2) + "\n")
        print(case, sha(folder / "proof.json"))


if __name__ == "__main__":
    main()
