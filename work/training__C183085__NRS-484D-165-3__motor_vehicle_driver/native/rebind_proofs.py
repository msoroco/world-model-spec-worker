"""Bind the current selected public, saved, and physical CPU receipts."""

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent.parent
NATIVE = ROOT / "native"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    path = ROOT / "selected-proof-manifest.json"
    manifest = json.loads(path.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].split("__")[-1]
        public = REPO / (".runtime-work/c183085-compat-v6-" + suffix)
        saved = REPO / (".runtime-work/c183085-saved-v6-" + suffix)
        sources = {
            "compatibility.json": "compatibility.json",
            "compatibility-analysis.log": "compatibility-analysis.log",
            "negative-analysis.log": "negative-analysis.log",
        }
        for source, ending in sources.items():
            shutil.copyfile(public / source, NATIVE / ("selected-" + suffix + "-" + ending))
        shutil.copyfile(saved / "v0001/processing.json",
                        NATIVE / ("selected-" + suffix + "-saved-processing.json"))
        receipt = NATIVE / ("selected-" + suffix + "-compatibility.json")
        negative = NATIVE / ("selected-" + suffix + "-negative-analysis.log")
        saved_receipt = NATIVE / ("selected-" + suffix + "-saved-processing.json")
        saved_log = NATIVE / ("selected-" + suffix + "-saved.log")
        entry["compatibility"] = {
            "receipt": str(receipt.relative_to(ROOT)),
            "log": "native/selected-" + suffix + "-compatibility-analysis.log",
            "negative_log": str(negative.relative_to(ROOT)),
            "sha256": sha(receipt),
        }
        entry["negative"] = {"log": str(negative.relative_to(ROOT)),
                             "log_sha256": sha(negative)}
        entry["post_capture"]["test_log_sha256"] = sha(saved_log)
        entry["post_capture"]["receipt_sha256"] = sha(saved_receipt)
        physical = NATIVE / ("physical-" + suffix + "/physical-preparation.json")
        physical_receipt = json.loads(physical.read_text())
        physical_receipt["lifecycle"]["source_compatibility_sha256"] = sha(receipt)
        write(physical, physical_receipt)
        entry["physical_preparation"]["sha256"] = sha(physical)
        print(suffix, sha(receipt), flush=True)
    write(path, manifest)
    print("manifest", sha(path))


if __name__ == "__main__":
    main()
