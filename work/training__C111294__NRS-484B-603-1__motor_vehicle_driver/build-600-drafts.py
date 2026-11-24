"""Build separate unselected 600-frame drafts, preserving 480-frame history."""
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


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def extend_trace(text):
    rows = [json.loads(line) for line in text.splitlines()]
    if len(rows) != 480 or [row["frame"] for row in rows] != list(range(480)):
        raise ValueError("Original 480-frame fixture changed")
    last = rows[-1]
    velocity = last["ego_velocity_mps"]
    other_step = [last["other_position_m"][i] - rows[-2]["other_position_m"][i]
                  for i in range(3)]
    for frame in range(480, 600):
        prior = rows[-1]
        row = dict(last)
        row["frame"] = frame
        row["t_s"] = round(frame / 20, 8)
        row["ego_position_m"] = [prior["ego_position_m"][i] + velocity[i] / 20
                                 for i in range(3)]
        row["other_position_m"] = [prior["other_position_m"][i] + other_step[i]
                                   for i in range(3)]
        rows.append(row)
    return "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)


def longer(path, text):
    if path.endswith(".py"):
        text = re.sub(r"\b480\b", "600", text)
        text = re.sub(r"\b479\b", "599", text)
        text = re.sub(r"\b24\b", "30", text)
    elif path.endswith("-synthetic-native.jsonl"):
        text = extend_trace(text)
    elif path == "config.json":
        config = json.loads(text)
        config["duration_s"] = 30
        config["knobs"]["duration_s"] = 30
        for channel in config["recording_description"]["channels"]:
            channel["time_window"] = "600 frames at 20 Hz"
        text = json.dumps(config, indent=2) + "\n"
    elif path == "draft-candidates.json":
        text = text.replace("480 frames", "600 frames")
    return text


def main():
    old = json.loads(ORIGINAL.read_text())
    new = {key: value for key, value in old.items() if key != "cases"}
    new["format"] = "worker-unselected-600-draft-construction-manifest-v1"
    new["source_manifest"] = ORIGINAL.name
    new["source_manifest_sha256"] = sha(ORIGINAL)
    new["cases"] = []
    for old_entry in old["cases"]:
        suffix = old_entry["case_id"].split("__")[-1]
        entry = {key: value for key, value in old_entry.items()
                 if key not in ("id", "construction", "construction_sha256", "candidates")}
        entry["candidates"] = []
        for candidate in CANDIDATES:
            original = HERE / "exact-drafts" / suffix / candidate / "construction.json"
            construction = json.loads(original.read_text())
            construction["files"] = [dict(file, content=longer(file["path"], file["content"]))
                                     for file in construction["files"]]
            for channel in construction["recording_description"]["channels"]:
                channel["time_window"] = "600 frames at 20 Hz"
            construction["measurement_plan"]["method"] = construction["measurement_plan"]["method"].replace("480", "600")
            construction["termination_rules"] = [rule.replace("480", "600")
                                                 for rule in construction["termination_rules"]]
            path = HERE / "duration-600-drafts" / suffix / candidate / "construction.json"
            write(path, construction)
            ref = {"id": candidate, "construction": str(path.relative_to(HERE)),
                   "construction_sha256": sha(path)}
            if candidate == "primary":
                entry.update(ref)
            else:
                old_ref = next(item for item in old_entry["candidates"] if item["id"] == candidate)
                ref["trigger"] = old_ref["trigger"]
                ref["changed_knobs"] = old_ref["changed_knobs"]
                entry["candidates"].append(ref)
        new["cases"].append(entry)
    write(OUTPUT, new)
    print(json.dumps({"cases": len(new["cases"]), "bundles": 8,
                      "manifest_sha256": sha(OUTPUT), "status": "unselected_600_frame_diagnostic"},
                     sort_keys=True))


if __name__ == "__main__":
    main()
