"""Rerun nine selected delivery audit diagnostics under current manifest sources."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    index = json.loads((HERE / "update042-nine-selected-index.json").read_text())
    if index["manifest_sha256"] != sha(HERE / "execution-manifest.json"):
        raise ValueError("Current selected matrix stale")
    outcomes = []
    for entry in manifest["cases"]:
        case = entry["case_id"]
        suffix = case.removeprefix(HERE.name + "__")
        folder = HERE / "update042-delivery-case-proofs" / suffix
        folder.mkdir(parents=True, exist_ok=True)
        contract = entry["delivery_acceptance"]
        for name, args, expected in (("positive", [], 0), ("negative", ["--negative"], 1)):
            command = [sys.executable, str(HERE / "prove-selected-delivery-case-update042.py"),
                       "--case", case, *args]
            run = subprocess.run(command, cwd=ROOT, text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            log = folder / (name + ".log")
            log.write_text(run.stdout)
            if run.returncode != expected:
                raise ValueError("Selected delivery CPU audit failed: " + case + "/" + name)
            static = HERE / contract["test_log" if name == "positive" else "negative_log"]
            bound_digest = contract["test_log_sha256" if name == "positive" else "negative_log_sha256"]
            if sha(static) != bound_digest:
                raise ValueError("Bound historical audit receipt changed: " + case)
            expected_text = '"source_shape_passed": true' if name == "positive" else "Delivery construction differs from selected manifest"
            if expected_text not in log.read_text() or expected_text not in static.read_text():
                raise ValueError("Current or bound diagnostic audit changed meaning: " + case)
        outcomes.append({"case_id": case, "positive_sha256": sha(folder / "positive.log"),
                         "negative_sha256": sha(folder / "negative.log"),
                         "delivery_accepted": False})
    proof = {"format": "c110454-current-manifest-delivery-audits-v1",
             "manifest_sha256": sha(HERE / "execution-manifest.json"),
             "cases": outcomes, "accepted_recordings": 0}
    path = HERE / "update042-selected-delivery-proof.json"
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"cases": len(outcomes), "accepted_recordings": 0,
                      "proof_sha256": sha(path)}))


if __name__ == "__main__":
    main()
