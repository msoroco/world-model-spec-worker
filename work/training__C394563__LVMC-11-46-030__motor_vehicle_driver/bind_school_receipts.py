"""Bind current positive and missing-source CPU compatibility receipts."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind(version, manifest_name="draft-native-manifest.json"):
    path = ROOT / manifest_name
    variant = manifest_name == "draft-variant-manifest.json"
    manifest = json.loads(path.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[1]
        for candidate in ("primary", "fallback1"):
            target = entry if candidate == "primary" else entry["candidates"][0]
            source_prefix = "c394563-variant-compat" if variant else "c394563-compat"
            source = REPO / ".runtime-work" / f"{source_prefix}-{suffix}-{candidate}-{version}"
            if not variant and not (source / "compatibility.json").is_file() and candidate == "primary" and suffix == "probe_1":
                source = REPO / ".runtime-work" / f"c394563-compat-{suffix}-{candidate}-v10"
            receipt = json.loads((source / "compatibility.json").read_text())
            if not receipt.get("passed") or receipt.get("construction_sha256") != target["construction_sha256"]:
                raise ValueError("Compatibility proof differs from exact construction")
            if receipt.get("negative_error_contains") not in (source / "negative-analysis.log").read_text():
                raise ValueError("Missing source rejection absent")
            prefix = ("variant-" if variant else "") + suffix + "-" + candidate
            destinations = {}
            for filename, label in (("compatibility.json", "receipt"),
                                    ("compatibility-analysis.log", "log"),
                                    ("negative-analysis.log", "negative_log")):
                destination = ROOT / "proofs" / (prefix + "-" + filename)
                destination.parent.mkdir(exist_ok=True)
                destination.write_bytes((source / filename).read_bytes())
                destinations[label] = str(destination.relative_to(ROOT))
            target["compatibility"] = {"receipt": destinations["receipt"],
                                       "sha256": sha(ROOT / destinations["receipt"]),
                                       "log": destinations["log"],
                                       "negative_log": destinations["negative_log"]}
        entry["negative"] = {"log": entry["compatibility"]["negative_log"]}
        construction = json.loads((ROOT / entry["construction"]).read_text())
        atoms = json.loads(next(item["content"] for item in construction["files"]
                                if item["path"] == "config.json"))["required_atoms"]
        channels = [item["name"] for item in construction["recording_description"]["channels"]]
        entry["acquisition"] = {name: {"entrypoint": "runner.py",
            "method": "original 20 Hz Native actor/camera source readback",
            "evidence": "native-rows.jsonl and video_frames.jsonl"}
            for name in atoms + channels}
        physical = ROOT / "proofs" / f"{'variant-' if variant else ''}{suffix}-physical-preparation.json"
        if physical.is_file():
            entry["physical_preparation"] = {"receipt": str(physical.relative_to(ROOT)),
                                             "sha256": sha(physical)}
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    return {"case_count": len(manifest["cases"]), "manifest_sha256": sha(path)}


if __name__ == "__main__":
    import sys
    print(json.dumps(bind(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "draft-native-manifest.json")))
