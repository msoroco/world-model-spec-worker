"""Advance all nine numeric/exception alternatives to the current capture profile."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAMES = {"intersection": "reference_corner", "parking": "driver_reference"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def adapt(item):
    path = item["path"]
    content = item["content"]
    if path == "measure_park.py":
        return {**item, "content": (HERE / "native/measure_park.py").read_text()}
    if path == "config.json":
        cfg = json.loads(content)
        cfg["duration_s"] = 30
        cfg["engineering_knobs"]["duration_s"] = 30.0
        cfg["engineering_knobs"]["camera_ids"] = [NAMES.get(x, x) for x in cfg["engineering_knobs"]["camera_ids"]]
        for camera in cfg["cameras"]:
            camera["name"] = NAMES.get(camera["name"], camera["name"])
        for channel in cfg["recording_description"]["channels"]:
            channel["time_window"] = "original 30 s / 600 frame attempt"
        content = json.dumps(cfg, indent=2) + "\n"
    elif path in ("runner.py", "cameras.py", "finalize.py", "measure_park.py") or path.startswith("tests/"):
        content = content.replace("('overview','approach','intersection','parking')",
                                  "('overview','approach','reference_corner','driver_reference')")
        content = content.replace('"intersection","parking"', '"reference_corner","driver_reference"')
        content = content.replace('"intersection"', '"reference_corner"') if path == "cameras.py" else content
        content = content.replace('"parking"', '"driver_reference"') if path == "cameras.py" else content
        if path == "runner.py":
            content = content.replace('config["duration_s"] != 24', 'config["duration_s"] != 30')
        if path == "finalize.py":
            witness_finalizer = (HERE / "native/finalize.py").read_text()
            start = witness_finalizer.index("def derive_channels_from_originals(")
            stop = witness_finalizer.index("\ndef finalize(", start)
            content = content.replace("def finalize(attempt,output):", witness_finalizer[start:stop] + "def finalize(attempt,output):")
            content = content.replace('def measure_case_sources(attempt):', 'def measure_case_sources(attempt, expected_frames):')
            content = content.replace('measure(source,sha(source))', 'measure(source,sha(source),expected_frames)')
            content = content.replace('measured=measure_case_sources(attempt)', 'measured=measure_case_sources(attempt,count)')
            content = content.replace("description=config['recording_description']", "description=config['recording_description']\n    derive_channels_from_originals(attempt,description,saved_motion,rows(attempt/'video_frames.jsonl'))")
            content = content.replace('original 24 s / 480 frame attempt', 'original 30 s / 600 frame attempt')
        if path.startswith("tests/"):
            content = content.replace('range(480)', 'range(600)').replace('i>=400', 'i>=500')
            content = content.replace('range(100,580)', 'range(100,700)')
            content = content.replace("'parking.mkv'", "'driver_reference.mkv'")
            content = content.replace('measure_case_sources(root)', 'measure_case_sources(root, 600)')
    if path == "exception_case.py":
        content = content.replace("'parking.mkv'", "'driver_reference.mkv'")
    return {**item, "content": content}


def main():
    result = {"format": "worker-unselected-current-profile-statutory-manifest",
              "assignment_id": HERE.name, "cases": []}
    for name in ("numeric", "exception"):
        original = json.loads((HERE / f"draft-{name}-execution-manifest.json").read_text())
        result["runtime_manifest_sha256"] = original["runtime_manifest_sha256"]
        for entry in original["cases"]:
            suffix = entry["case_id"].rsplit("__", 1)[-1]
            updated_entry = {**entry, "candidates": []}
            for candidate in (entry, *entry["candidates"][:2]):
                old = json.loads((HERE / candidate["construction"]).read_text())
                current = {**old, "files": [adapt(item) for item in old["files"]]}
                for channel in current["recording_description"]["channels"]:
                    channel["time_window"] = "original 30 s / 600 frame attempt"
                current["static_checks"] = [x.replace("480-frame", "600-frame") for x in current["static_checks"]]
                current["termination_rules"] = [x.replace("480 original frames", "600 original frames") for x in current["termination_rules"]]
                current["status"] = "unselected_current_profile_statutory_draft"
                output = HERE / "draft-current-statutory" / suffix / candidate["id"] / "construction.json"
                write(output, current)
                updated_candidate = {**candidate, "construction": str(output.relative_to(HERE)),
                                     "construction_sha256": sha(output)}
                if candidate is entry:
                    updated_entry["construction"] = updated_candidate["construction"]
                    updated_entry["construction_sha256"] = updated_candidate["construction_sha256"]
                else:
                    updated_entry["candidates"].append(updated_candidate)
            result["cases"].append(updated_entry)
    target = HERE / "current-profile-statutory-manifest.json"
    write(target, result)
    print(json.dumps({"cases": len(result["cases"]),
                      "candidates": sum(1 + len(x["candidates"]) for x in result["cases"]),
                      "manifest_sha256": sha(target)}))


if __name__ == "__main__":
    main()
