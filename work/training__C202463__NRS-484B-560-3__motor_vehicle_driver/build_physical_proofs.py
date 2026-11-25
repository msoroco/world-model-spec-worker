"""Run three source-shaped stop outcomes and lifecycle check per selected case."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    for entry in manifest["cases"]:
        condition = entry["case_id"].rsplit("__", 1)[1]
        directory = HERE / "proofs" / "physical" / condition
        directory.mkdir(parents=True, exist_ok=True)
        fixtures = []
        lifecycle = None
        for kind in ("complete_motion", "incomplete_motion",
                     "missing_evidence", "lifecycle"):
            result = directory / (kind + ".json")
            log = directory / (kind + ".log")
            command = [sys.executable, str(HERE / "physical_fixture.py"),
                       "--condition", condition, "--kind", kind,
                       "--output", str(result)]
            with log.open("w") as stream:
                finished = subprocess.run(command, cwd=HERE.parents[1],
                                          env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
                                          stdout=stream, stderr=subprocess.STDOUT)
            if finished.returncode:
                raise ValueError("Physical fixture failed: " + condition + " " + kind)
            item = {"command": " ".join(command), "exit_code": 0,
                    "log": str(log.relative_to(HERE)), "log_sha256": sha(log)}
            if kind == "lifecycle":
                lifecycle = dict(item, events=json.loads(result.read_text())["events"])
            else:
                item.update(kind=kind, result=str(result.relative_to(HERE)),
                            result_sha256=sha(result))
                fixtures.append(item)
        proof = {"format": "c202463-physical-preparation-v1",
                 "case_id": entry["case_id"],
                 "construction_sha256": entry["construction_sha256"],
                 "fixtures": fixtures, "lifecycle": lifecycle,
                 "original_native_executed": False,
                 "physical_completion_claimed": False}
        write(directory / "proof.json", proof)
    print(json.dumps({"passed": True, "cases": len(manifest["cases"])}))


if __name__ == "__main__":
    main()
