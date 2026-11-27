"""Retain exact primary source-bound compatibility receipts in the assignment."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def main():
    manifest_path = HERE / "draft-native-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        slug = entry["case_id"].rsplit("__", 1)[-1]
        label = slug
        source = REPO / ".runtime-work" / "c111343-yield" / ("compat-" + label + "-primary-v10")
        source_receipt = source / "compatibility.json"
        if not source_receipt.is_file():
            raise ValueError("Current-runtime compatibility proof missing: " + slug)
        receipt = json.loads(source_receipt.read_text())
        for original, target in (("compatibility-analysis.log", "cpu-compat-" + slug + "-analysis.log"),
                                 ("negative-analysis.log", "cpu-compat-" + slug + "-negative.log")):
            (HERE / target).write_text((source / original).read_text().rstrip() + "\n")
        receipt["log_sha256"] = sha(HERE / ("cpu-compat-" + slug + "-analysis.log"))
        receipt["negative_log_sha256"] = sha(HERE / ("cpu-compat-" + slug + "-negative.log"))
        receipt_path = HERE / ("cpu-compat-" + slug + ".json")
        put(receipt_path, receipt)
        entry["compatibility"] = {"receipt": receipt_path.name,
            "sha256": sha(receipt_path), "log": "cpu-compat-" + slug + "-analysis.log"}
        entry["negative"] = {"log": "cpu-compat-" + slug + "-negative.log"}
        entry["acquisition"] = {
            "ego_pose": {"entrypoint": "finalize.py",
                         "method": "original same-frame subject transform and body source",
                         "evidence": "channels/ego_pose.jsonl"},
            "conditional_stop_position": {"entrypoint": "finalize.py",
                "method": "original front-bumper first rest versus selected map-readback stopping reference",
                "evidence": "channels/conditional_stop_position.jsonl"}}
        physical = HERE / "physical-proof" / slug / "proof.json"
        if physical.is_file():
            entry["physical_preparation"] = {"receipt": str(physical.relative_to(HERE)),
                                             "sha256": sha(physical)}
        fallback = entry["candidates"][0]
        fallback_source = REPO / ".runtime-work" / "c111343-yield" / ("compat-" + label + "-fallback1-v10")
        fallback_receipt = json.loads((fallback_source / "compatibility.json").read_text())
        for original, target in (("compatibility-analysis.log", "cpu-compat-" + slug + "-fallback1-analysis.log"),
                                 ("negative-analysis.log", "cpu-compat-" + slug + "-fallback1-negative.log")):
            (HERE / target).write_text((fallback_source / original).read_text().rstrip() + "\n")
        fallback_receipt["log_sha256"] = sha(HERE / ("cpu-compat-" + slug + "-fallback1-analysis.log"))
        fallback_receipt["negative_log_sha256"] = sha(HERE / ("cpu-compat-" + slug + "-fallback1-negative.log"))
        fallback_receipt_path = HERE / ("cpu-compat-" + slug + "-fallback1.json")
        put(fallback_receipt_path, fallback_receipt)
        fallback["compatibility"] = {"receipt": fallback_receipt_path.name,
            "sha256": sha(fallback_receipt_path),
            "log": "cpu-compat-" + slug + "-fallback1-analysis.log",
            "negative_log": "cpu-compat-" + slug + "-fallback1-negative.log"}
    put(manifest_path, manifest)
    return {"cases": len(manifest["cases"]), "manifest_sha256": sha(manifest_path)}


if __name__ == "__main__":
    print(json.dumps(main(), sort_keys=True))
