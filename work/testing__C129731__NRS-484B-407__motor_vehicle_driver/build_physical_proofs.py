"""Run three pinned turn classifier fixtures and one lifecycle fixture per case."""
import hashlib
import json
from pathlib import Path
import shlex
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASES = (
    ("curve-short", "curve", "short_of_500ft", "diagnostic-execution-manifest.json", "processing.json"),
    ("at", "curve", "at_500ft", "diagnostic-at-manifest.json", "rebound-at-processing.json"),
    ("beyond", "curve", "beyond_500ft", "diagnostic-beyond-manifest.json", "rebound-beyond-processing.json"),
    ("crest-short", "crest", "short_of_500ft", "diagnostic-crest-short-manifest.json", "rebound-crest-short-processing.json"),
    ("crest-at", "crest", "at_500ft", "diagnostic-crest-at-manifest.json", "rebound-crest-at-processing.json"),
    ("crest-beyond", "crest", "beyond_500ft", "diagnostic-crest-beyond-manifest.json", "rebound-crest-beyond-processing.json"),
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rel(path):
    return str(Path(path).relative_to(HERE))


def run_one(slug, feature, probe, manifest_name, saved_name, case_id=None):
    manifest = HERE / manifest_name
    case_id = case_id or HERE.name + "__" + feature + "__" + probe
    entry = next(e for e in json.loads(manifest.read_text())["cases"] if e["case_id"] == case_id)
    target = HERE / "physical-proofs" / slug
    target.mkdir(parents=True, exist_ok=True)
    fixtures = []
    for kind in ("complete_motion", "incomplete_motion", "missing_evidence"):
        result = target / (kind + ".json")
        log = target / (kind + ".log")
        args = [str(ROOT / ".venv-cpu/bin/python"), str(HERE / "physical_fixture_proof.py"),
                "--manifest", str(manifest), "--case", case_id, "--kind", kind, "--output", str(result)]
        process = subprocess.run(args, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 text=True, timeout=180)
        log.write_text(process.stdout)
        if process.returncode:
            raise ValueError("Physical fixture failed: " + case_id + " " + kind + " " + process.stdout[-600:])
        fixtures.append({"kind": kind, "command": shlex.join(args), "exit_code": process.returncode,
                         "log": rel(log), "log_sha256": sha(log),
                         "result": rel(result), "result_sha256": sha(result)})
    result = target / "lifecycle.json"
    log = target / "lifecycle.log"
    saved = HERE / saved_name
    args = [str(ROOT / ".venv-cpu/bin/python"), str(HERE / "physical_fixture_proof.py"),
            "--manifest", str(manifest), "--case", case_id, "--kind", "lifecycle",
            "--saved", str(saved), "--output", str(result)]
    process = subprocess.run(args, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, timeout=180)
    log.write_text(process.stdout)
    if process.returncode:
        raise ValueError("Lifecycle fixture failed: " + case_id + " " + process.stdout[-600:])
    life = json.loads(result.read_text())
    life.update({"command": shlex.join(args), "exit_code": process.returncode,
                 "log": rel(log), "log_sha256": sha(log)})
    receipt = {"format": "worker-physical-preparation", "case_id": case_id,
               "construction_sha256": entry["construction_sha256"], "fixtures": fixtures,
               "lifecycle": life, "scope": "synthetic CPU classifier and ownership proof only"}
    receipt_path = target / "receipt.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"case_id": case_id, "receipt": rel(receipt_path), "sha256": sha(receipt_path)}))


if __name__ == "__main__":
    for row in CASES:
        run_one(*row)
