"""Generate explicit synthetic police-source diagnostic fixtures; no Native claim."""
import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
BASE = ROOT / "selected-source/condition_a"
FILES = ("acquisition-provenance.json", "capture/evidence.jsonl", "capture/manifest.json",
         "capture/native/frames.jsonl", "capture/recorder_info.txt", "trace.jsonl",
         "video_frames.jsonl", "road.xodr", "obstruction-inventory.json",
         "native_samples.jsonl", "camera-frames.jsonl")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def build(suffix):
    if suffix not in ("police_absent", "police_present"):
        raise ValueError("Unknown exact police source branch")
    case = ROOT.name + "__selected_police_source__" + suffix
    target = ROOT / "selected-source" / suffix
    target.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        dest = target / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(BASE / name, dest)
    flags = {name: False for name in ("traffic_conflict", "law_direction",
                                       "police_direction", "traffic_device")}
    flags["police_direction"] = suffix == "police_present"
    reviewed = {name + "_reviewed": True for name in flags}
    write(target / "exception-context.json", {
        "case_id": case, "source_kind": "synthetic_cpu",
        "activity_request": "park",
        "exception_request": "police_direction" if suffix == "police_present" else None,
        "exceptions": flags, "exception_source": reviewed,
        "legal_verdict_claimed": False})
    inventory = json.loads((target / "obstruction-inventory.json").read_text())
    inventory["case_id"] = case
    write(target / "obstruction-inventory.json", inventory)
    samples = [json.loads(row) for row in (target / "native_samples.jsonl").read_text().splitlines()]
    for row in samples:
        row["exceptions"] = flags
        row["exception_source"] = reviewed
        row["activity_request"] = "park"
    (target / "native_samples.jsonl").write_text("".join(json.dumps(row) + "\n" for row in samples))
    cameras = [json.loads(row) for row in (target / "camera-frames.jsonl").read_text().splitlines()]
    for row in cameras:
        row["rgb_sha256"] = hashlib.sha256((case + ":" + str(row["frame"]) + ":" + row["camera"]).encode()).hexdigest()
    (target / "camera-frames.jsonl").write_text("".join(json.dumps(row) + "\n" for row in cameras))
    names = FILES + ("exception-context.json",)
    recipe = {"format": "worker-fixture-recipe", "sources": [
        {"path": name, "source": str((target / name).relative_to(REPO)),
         "sha256": sha(target / name)} for name in names],
        "generator": {"source": str((ROOT / "selected-generator.json").relative_to(REPO)),
                      "sha256": sha(ROOT / "selected-generator.json")}}
    write(ROOT / ("selected-recipe-" + suffix + ".json"), recipe)
    return {"case_id": case, "fixture_source_count": len(names),
            "recipe_sha256": sha(ROOT / ("selected-recipe-" + suffix + ".json")),
            "synthetic_only": True}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--suffix", choices=("police_absent", "police_present"), required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.suffix)))
