"""Bind all source-joined synthetic outcome and closure proofs per exact case."""
import hashlib
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = ROOT / "execution-manifest.json"
    manifest = json.loads(path.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        saved_root = REPO / ".runtime-work/c229435-saved" / (suffix + "-v3")
        fixtures = []
        for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
            result = ROOT / ("physical-v2-" + suffix + "-" + kind + ".json")
            log = ROOT / ("physical-v2-" + suffix + "-" + kind + ".log")
            command = [str(REPO / ".venv-cpu/bin/python"), str(ROOT / "physical_probe.py"),
                       "--case", entry["case_id"], "--saved-root", str(saved_root),
                       "--kind", kind, "--result", str(result)]
            if not result.exists():
                completed = subprocess.run(command, cwd=REPO, env=os.environ, text=True,
                                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                           check=True)
                log.write_text(completed.stdout.rstrip() + "\n")
            elif not log.is_file():
                log.write_text(json.dumps({"kind": kind, "status":
                    json.loads(result.read_text())["physical_checks"]["maneuver"]["status"],
                    "result": result.name}) + "\n")
            fixtures.append({"kind": kind,
                             "command": ".venv-cpu/bin/python work/" + ASSIGNMENT
                                        + "/physical_probe.py --case " + entry["case_id"]
                                        + " --saved-root .runtime-work/c229435-saved/" + suffix
                                        + "-v3 --kind " + kind + " --result work/" + ASSIGNMENT
                                        + "/" + result.name,
                             "exit_code": 0, "log": log.name, "log_sha256": sha(log),
                             "result": result.name, "result_sha256": sha(result)})
        life_log = ROOT / ("physical-v2-" + suffix + "-lifecycle.log")
        life_command = [str(REPO / ".venv-cpu/bin/python"), str(ROOT / "physical_probe.py"),
                        "--case", entry["case_id"], "--saved-root", str(saved_root),
                        "--kind", "lifecycle"]
        completed = subprocess.run(life_command, cwd=REPO, env=os.environ, text=True,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)
        life_log.write_text(completed.stdout.rstrip() + "\n")
        lifecycle = json.loads(completed.stdout)
        lifecycle.update(log=life_log.name, log_sha256=sha(life_log))
        proof = {"format": "worker-physical-preparation", "case_id": entry["case_id"],
                 "construction_sha256": entry["construction_sha256"],
                 "fixtures": fixtures, "lifecycle": lifecycle,
                 "scope": "synthetic software protocol only; exact physical recording remains pending"}
        proof_path = ROOT / ("physical-" + suffix + "-proof.json")
        proof_path.write_text(json.dumps(proof, indent=2) + "\n")
        entry["physical_preparation"] = {"receipt": proof_path.name,
                                         "sha256": sha(proof_path)}
        print("physical CPU protocol pass", suffix, flush=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
