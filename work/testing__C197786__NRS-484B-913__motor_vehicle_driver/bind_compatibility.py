"""Bind completed current-runtime fixture receipts to selected exact cases."""

import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for case in manifest["cases"]:
        short = case["case_id"].removeprefix(ROOT.name + "__")
        output = REPO / ".runtime-work" / ("hose-913-compat-" + short + "-v3")
        receipt = json.loads((output / "compatibility.json").read_text())
        if (receipt.get("passed") is not True or receipt.get("case_id") != case["case_id"]
                or receipt.get("construction_sha256") != case["construction_sha256"]
                or receipt.get("runtime_manifest_sha256") != manifest["runtime_manifest_sha256"]):
            raise ValueError("incomplete or stale exact compatibility: " + short)
        folder = ROOT / "cases" / short
        copy = {"compatibility.json": "compatibility.json",
                "compatibility-analysis.log": "cpu-compatibility-analysis.log",
                "negative-analysis.log": "negative-analysis.log"}
        for source, target in copy.items():
            shutil.copyfile(output / source, folder / target)
        case["compatibility"] = {
            "receipt": str((folder / "compatibility.json").relative_to(ROOT)),
            "sha256": sha(folder / "compatibility.json"),
            "log": str((folder / "cpu-compatibility-analysis.log").relative_to(ROOT))}
        case["negative"] = {"log": str((folder / "negative-analysis.log").relative_to(ROOT))}
        print(short, "passed")
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
