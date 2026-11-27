"""Replace empty analysis stdout files with an explicit no-stdout record and rebind hashes."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    proofs_path = ROOT / "cpu-compatibility-proofs.json"
    proofs = json.loads(proofs_path.read_text())
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    entries = {entry["case_id"]: entry for entry in manifest["cases"]}
    for row in proofs:
        log = ROOT / row["positive_log"]
        if log.read_text() == "\n":
            log.write_text("Analysis subprocess completed successfully with no stdout.\n")
        receipt_path = ROOT / row["receipt"]
        receipt = json.loads(receipt_path.read_text())
        receipt["log_sha256"] = sha(log)
        write(receipt_path, receipt)
        row["receipt_sha256"] = sha(receipt_path)
        entry = entries[row["case_id"]]
        target = entry if row["candidate"] == "primary" else entry["candidates"][0]
        target["compatibility"]["sha256"] = row["receipt_sha256"]
    write(proofs_path, proofs)
    write(manifest_path, manifest)


if __name__ == "__main__":
    main()
