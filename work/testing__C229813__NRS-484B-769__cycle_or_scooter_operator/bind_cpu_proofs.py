"""Bind exact offline and compatibility CPU proofs into the draft manifest."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / "execution-manifest.draft.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n")


def copy_log(source, destination):
    destination.write_bytes(source.read_bytes().rstrip() + b"\n")
    return sha(destination)


def main():
    manifest = json.loads(MANIFEST.read_text())
    offline = {(item["case_id"], item["candidate_id"]): item
               for item in json.loads((ROOT / "cpu-offline-proofs.json").read_text())}
    compatibility = {(item["case_id"], item["candidate_id"]): item
                     for item in json.loads((ROOT / "cpu-compatibility-proofs.json").read_text())["results"]}
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        suffix = case_id.removeprefix(ROOT.name + "__")
        for candidate_id, selected in [("primary", entry)] + [
                (item["id"], item) for item in entry["candidates"]]:
            proof = dict(offline[(case_id, candidate_id)])
            proof.pop("case_id")
            proof.pop("candidate_id")
            selected["offline"] = proof
            run = compatibility[(case_id, candidate_id)]
            source = REPO / run["receipt"]
            receipt = json.loads(source.read_text())
            local_prefix = f"proof-compatibility-{suffix}-{candidate_id}"
            positive_log = ROOT / (local_prefix + "-analysis.log")
            negative_log = ROOT / (local_prefix + "-negative.log")
            receipt["log_sha256"] = copy_log(source.parent / "compatibility-analysis.log", positive_log)
            receipt["negative_log_sha256"] = copy_log(source.parent / "negative-analysis.log", negative_log)
            receipt_path = ROOT / (local_prefix + "-receipt.json")
            write(receipt_path, receipt)
            selected["compatibility"] = {"command": run["command"],
                "receipt": receipt_path.name, "sha256": sha(receipt_path),
                "log": positive_log.name, "negative_log": negative_log.name}
            if candidate_id == "primary":
                entry["negative"] = {"log": negative_log.name}
    write(MANIFEST, manifest)
    print("bound", len(manifest["cases"]), "primary and fallback proof pairs")


if __name__ == "__main__":
    main()
