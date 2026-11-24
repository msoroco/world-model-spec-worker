"""Replay selected source audits against the current eight-path matrix."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args, name, expected):
    log = HERE / name
    with log.open("w") as stream:
        code = subprocess.run([sys.executable, *map(str, args)], cwd=ROOT,
                              stdout=stream, stderr=subprocess.STDOUT).returncode
    if code != expected:
        raise RuntimeError(f"{name}: expected exit {expected}, received {code}")
    return sha(log)


def main():
    matrix = json.loads((HERE / "owner104-recording-matrix-proof.json").read_text())
    manifest = json.loads((HERE / "execution-manifest.json").read_text())
    sources = {name: sha(HERE / name) for name in
               ("audit-selected-delivery.py", "audit-selected-comparison.py")}
    pair = []
    for entry, label in zip(manifest["cases"], ("a", "b")):
        path = matrix["paths"][label + "-primary"]
        attempt = ROOT / path["attempt"]
        saved = ROOT / path["saved"] / "v0001"
        pair.extend((attempt, saved))
        command = [HERE / "audit-selected-delivery.py", "--case", entry["case_id"],
                   "--attempt", attempt, "--saved", saved]
        for suffix, extra, code in (("positive", [], 0),
                                    ("negative", ["--remove-native-source"], 1)):
            name = f"owner104-delivery-{label}-{suffix}.log"
            sources[name] = run(command + extra, name, code)
    command = [HERE / "audit-selected-comparison.py", "--attempt-a", pair[0],
               "--saved-a", pair[1], "--attempt-b", pair[2], "--saved-b", pair[3]]
    for suffix, extra, code in (("positive", [], 0),
                                ("negative", ["--reject-road-drift"], 1)):
        name = f"owner104-comparison-{suffix}.log"
        sources[name] = run(command + extra, name, code)
    proof = {"format": "c110763-owner104-selected-audits-v1", "passed": True,
             "physical_observation_claimed": False, "source_files": sources,
             "delivery_positive_cases": 2, "delivery_negative_cases": 2,
             "comparison_positive": True, "comparison_road_drift_rejected": True}
    path = HERE / "owner104-selected-audits-proof.json"
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"proof": path.name, "sha256": sha(path)}))


if __name__ == "__main__":
    main()
