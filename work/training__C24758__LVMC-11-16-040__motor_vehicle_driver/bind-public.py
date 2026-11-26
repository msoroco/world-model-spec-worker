"""Bind six pinned public CPU receipts to the exact draft selection."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind(suffix, candidate):
    source = REPO / ".runtime-work" / f"c24758-{suffix}-{candidate}-final2-public-20261125"
    target = ROOT / "proofs" / suffix / candidate
    target.mkdir(parents=True, exist_ok=True)
    for name in ("compatibility.json", "negative-analysis.log"):
        shutil.copyfile(source / name, target / name)
    shutil.copyfile(source / "compatibility-analysis.log", target / "public-analysis.log")
    receipt = json.loads((target / "compatibility.json").read_text())
    if receipt["case_id"] != ROOT.name + "__" + suffix or receipt["candidate_id"] != candidate:
        raise ValueError("Public receipt selects another exact candidate")
    if receipt["log_sha256"] != sha(target / "public-analysis.log") or \
            receipt["negative_log_sha256"] != sha(target / "negative-analysis.log"):
        raise ValueError("Public log binding changed")
    return {"receipt": str((target / "compatibility.json").relative_to(ROOT)),
            "sha256": sha(target / "compatibility.json"),
            "log": str((target / "public-analysis.log").relative_to(ROOT)),
            "negative_log": str((target / "negative-analysis.log").relative_to(ROOT))}


def main():
    manifest_path = ROOT / "draft-execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        entry["compatibility"] = bind(suffix, "primary")
        entry["negative"] = {"log": entry["compatibility"]["negative_log"],
                             "log_sha256": sha(ROOT / entry["compatibility"]["negative_log"])}
        for fallback in entry["candidates"]:
            fallback["compatibility"] = bind(suffix, fallback["id"])
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print("bound", len(manifest["cases"]), "primary and", sum(len(x["candidates"]) for x in manifest["cases"]), "fallback receipts")


if __name__ == "__main__":
    main()
