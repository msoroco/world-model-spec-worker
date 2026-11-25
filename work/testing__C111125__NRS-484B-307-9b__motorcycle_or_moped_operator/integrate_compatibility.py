"""Copy a passed diagnostic compatibility receipt into the assignment package."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys


def sha(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def main(suffix: str, output: Path) -> None:
    folder = Path(__file__).resolve().parent
    proof = json.loads((output / "compatibility.json").read_text())
    if not proof.get("passed") or not proof["case_id"].endswith("__" + suffix):
        raise ValueError("Compatibility proof did not pass for selected case")
    for source, target, key in (
        ("compatibility-analysis.log", f"compat-{suffix}-analysis.log", "log_sha256"),
        ("negative-analysis.log", f"compat-{suffix}-negative.log", "negative_log_sha256"),
    ):
        clean = "\n".join(line.rstrip() for line in (output / source).read_text().rstrip().splitlines()) + "\n"
        (folder / target).write_text(clean)
        proof[key] = sha(clean.encode())
    receipt = folder / f"compat-{suffix}-receipt.json"
    receipt.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")
    manifest = folder / "execution-manifest.json"
    data = json.loads(manifest.read_text())
    entry = next(row for row in data["cases"] if row["case_id"].endswith("__" + suffix))
    entry["compatibility"] = {
        "receipt": receipt.name,
        "sha256": sha(receipt.read_bytes()),
        "log": f"compat-{suffix}-analysis.log",
    }
    entry["negative"] = {"log": f"compat-{suffix}-negative.log"}
    manifest.write_text(json.dumps(data, indent=2) + "\n")
    print(suffix, "integrated", receipt.stat().st_size)


if __name__ == "__main__":
    main(sys.argv[1], Path(sys.argv[2]))
