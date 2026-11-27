"""Copy exact current-runtime public compatibility receipts into the package."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
AID = ROOT.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind():
    path = ROOT / "draft-native-manifest.json"
    manifest = json.loads(path.read_text())
    for entry in manifest["cases"]:
        slug = entry["case_id"].removeprefix(AID + "__")
        source = REPO / ".runtime-work/bus-c378131" / ("compat-" + slug + "-v3")
        receipt_path = source / "compatibility.json"
        if not receipt_path.is_file():
            raise ValueError("exact compatibility receipt missing: " + slug)
        receipt = json.loads(receipt_path.read_text())
        if receipt["case_id"] != entry["case_id"] or receipt["construction_sha256"] != entry[
                "construction_sha256"] or receipt["passed"] is not True:
            raise ValueError("stale exact compatibility receipt: " + slug)
        for original, target in (("compatibility-analysis.log", "cpu-compat-" + slug + "-analysis.log"),
                                 ("negative-analysis.log", "cpu-compat-" + slug + "-negative.log")):
            (ROOT / target).write_text((source / original).read_text().rstrip() + "\n")
        receipt["log_sha256"] = sha(ROOT / ("cpu-compat-" + slug + "-analysis.log"))
        receipt["negative_log_sha256"] = sha(ROOT / ("cpu-compat-" + slug + "-negative.log"))
        copy = ROOT / ("cpu-compat-" + slug + ".json")
        copy.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n")
        entry["compatibility"] = {"receipt": copy.name, "sha256": sha(copy),
                                  "log": "cpu-compat-" + slug + "-analysis.log"}
        entry["negative"] = {"log": "cpu-compat-" + slug + "-negative.log"}
        entry["acquisition"] = {channel["name"]: {
            "entrypoint": "finalize.py",
            "method": "source-hashed original Native bus, passenger, map and camera frame join",
            "evidence": "channels/" + channel["name"] + ".jsonl"}
            for channel in entry["recording_description"]["channels"]}
    path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + "\n")
    return len(manifest["cases"])


if __name__ == "__main__":
    print(bind())
