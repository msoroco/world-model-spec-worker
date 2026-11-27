"""Bind only passing selected sweep compatibility receipts, retaining older cases."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / ".runtime-work/c386226-5071-compat-sweep"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    path = HERE / "execution-manifest.json"
    manifest = json.loads(path.read_text())
    entries = [entry for entry in manifest["cases"] if "__sweep_" in entry["case_id"]]
    if len(entries) != 15:
        raise ValueError("expected exactly 15 selected sweep entries")
    for entry in entries:
        name = entry["case_id"].removeprefix(HERE.name + "__")
        source = SOURCE / (name + "-v4")
        receipt = json.loads((source / "compatibility.json").read_text())
        if (receipt.get("passed") is not True or receipt.get("case_id") != entry["case_id"]
                or receipt.get("construction_sha256") != entry["construction_sha256"]):
            raise ValueError("selected sweep compatibility did not pass: " + name)
        target = HERE / "proofs" / ("selected-" + name)
        target.mkdir(parents=True, exist_ok=True)
        for original, copied in (("compatibility.json", "receipt.json"),
                                 ("compatibility-analysis.log", "analysis.log"),
                                 ("negative-analysis.log", "negative.log")):
            raw = (source / original).read_bytes()
            if raw.endswith(b"\n\n") or any(line.rstrip(b" \t\r") != line for line in raw.split(b"\n")):
                raise ValueError("compatibility proof has trailing whitespace: " + name + "/" + original)
            (target / copied).write_bytes(raw)
        entry["compatibility"] = {"receipt": str((target / "receipt.json").relative_to(HERE)),
                                  "sha256": sha(target / "receipt.json"),
                                  "log": str((target / "analysis.log").relative_to(HERE))}
        entry["negative"] = {"log": str((target / "negative.log").relative_to(HERE))}
    manifest["status"] = "selected_compatibility_bound_saved_proofs_pending"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    print("bound 15 passing sweep compatibility receipts")


if __name__ == "__main__":
    main()
