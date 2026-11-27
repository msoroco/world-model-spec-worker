"""Bind completed physical receipts after concurrent compatibility manifest update."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
path = root / "execution-manifest.json"
manifest = json.loads(path.read_text())
for entry in manifest["cases"]:
    suffix = entry["case_id"].split("__")[-1]
    receipt = root / ("physical-preparation-" + suffix + ".json")
    proof = json.loads(receipt.read_text())
    if proof["case_id"] != entry["case_id"] or proof["construction_sha256"] != entry["construction_sha256"]:
        raise ValueError("Physical receipt binding differs")
    entry["physical_preparation"] = {"receipt": receipt.name,
                                     "sha256": hashlib.sha256(receipt.read_bytes()).hexdigest()}
path.write_text(json.dumps(manifest, indent=2) + "\n")
