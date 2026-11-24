"""Derive separate unselected 30-second drafts from the retained 24-second code.

The existing 480-frame packages and receipts remain historical diagnostics. This
script writes eight new 600-frame exact construction bundles; it makes no claim
about original CARLA motion or current-runtime saved compatibility.
"""
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORIGINAL = HERE / "draft-execution-manifest.json"
OUTPUT = HERE / "draft-execution-manifest-600.json"
CANDIDATES = ("primary", "fallback1", "fallback2", "fallback3")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def long_content(name, content):
    if name.endswith(".py"):
        content = re.sub(r"\b480\b", "600", content)
        content = re.sub(r"\b479\b", "599", content)
        content = re.sub(r"\b24\b", "30", content)
    elif name == "config.json":
        obj = json.loads(content)
        obj["duration_s"] = 30
        obj["engineering_knobs"]["duration_s"] = 30
        for channel in obj["recording_description"]["channels"]:
            channel["time_window"] = "30 s / 600 joined frames"
        content = json.dumps(obj, indent=2) + "\n"
    return content


def main():
    old = json.loads(ORIGINAL.read_text())
    new = {key: value for key, value in old.items() if key != "cases"}
    new["format"] = "worker-unselected-600-draft-construction-manifest-v1"
    new["status"] = "draft_not_selected"
    new["source_manifest"] = ORIGINAL.name
    new["source_manifest_sha256"] = sha(ORIGINAL)
    new["cases"] = []
    for old_entry in old["cases"]:
        suffix = old_entry["case_id"].split("__")[-1]
        entry = {key: value for key, value in old_entry.items()
                 if key not in ("id", "construction", "construction_sha256", "candidates")}
        entry["candidates"] = []
        for candidate in CANDIDATES:
            source = HERE / "draft-candidates" / suffix / candidate / "construction.json"
            construction = json.loads(source.read_text())
            construction["files"] = [dict(file, content=long_content(file["path"], file["content"]))
                                     for file in construction["files"]]
            for channel in construction["recording_description"]["channels"]:
                channel["time_window"] = "30 s / 600 joined frames"
            construction["static_checks"] = [text.replace("480", "600") for text in construction["static_checks"]]
            construction["termination_rules"] = [text.replace("480", "600") for text in construction["termination_rules"]]
            output = HERE / "duration-600-drafts" / suffix / candidate / "construction.json"
            write(output, construction)
            ref = {"id": candidate, "construction": str(output.relative_to(HERE)),
                   "construction_sha256": sha(output)}
            if candidate == "primary":
                entry.update(ref)
            else:
                old_ref = next(item for item in old_entry["candidates"] if item["id"] == candidate)
                ref["trigger"] = old_ref["trigger"]
                ref["changed_knobs"] = old_ref["changed_knobs"]
                entry["candidates"].append(ref)
        new["cases"].append(entry)
    write(OUTPUT, new)
    print(json.dumps({"manifest": str(OUTPUT.relative_to(HERE)), "sha256": sha(OUTPUT),
                      "cases": len(new["cases"]), "candidate_bundles": 8,
                      "status": "unselected_600_frame_diagnostic"}, sort_keys=True))


if __name__ == "__main__":
    main()
