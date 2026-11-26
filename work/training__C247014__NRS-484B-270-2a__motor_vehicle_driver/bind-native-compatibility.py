"""Bind exact public compatibility receipts and acquisition sources."""

import hashlib
import json
import shutil
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MANIFEST = HERE / "selected-native-draft-manifest.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].split("__")[-1]
        source = REPO / ".runtime-work" / ("c247014-compat-" + suffix + "-v4")
        receipt = json.loads((source / "compatibility.json").read_text())
        if (receipt.get("case_id") != entry["case_id"] or
                receipt.get("candidate_id") != "primary" or
                receipt.get("construction_sha256") != entry["construction_sha256"] or
                receipt.get("passed") is not True):
            raise ValueError("Exact public compatibility identity differs: " + suffix)
        dest = HERE / "selected-native-draft" / suffix / "public-proof"
        dest.mkdir(exist_ok=True)
        for original, target in (("compatibility.json", "receipt.json"),
                                 ("compatibility-analysis.log", "analysis.log"),
                                 ("negative-analysis.log", "negative.log")):
            shutil.copyfile(source / original, dest / target)
        entry["compatibility"] = {
            "receipt": str((dest / "receipt.json").relative_to(HERE)),
            "sha256": sha(dest / "receipt.json"),
            "log": str((dest / "analysis.log").relative_to(HERE))}
        entry["negative"] = {
            "log": str((dest / "negative.log").relative_to(HERE))}
        construction = json.loads((HERE / entry["construction"]).read_text())
        config = json.loads(next(item["content"] for item in construction["files"]
                                 if item["path"] == "config.json"))
        required = set(config["required_atoms"])
        required.update(c["name"] for c in construction["recording_description"]["channels"])
        entry["acquisition"] = {
            atom: {"entrypoint": "runner.py",
                   "method": "original Native same-tick actor and camera capture with saved source join",
                   "evidence": "participant-poses.jsonl, video_frames.jsonl, trace.jsonl and capture/evidence.jsonl"}
            for atom in sorted(required)}
    MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"bound": len(manifest["cases"]), "manifest_sha256": sha(MANIFEST)},
                     sort_keys=True))


if __name__ == "__main__":
    main()
