"""Bind exact source paths for every required Core and saved crosswalk term."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / "execution-manifest.json"
    manifest = json.loads(path.read_text())
    sources = {
        "ru.pedestrian": ("runner.py", "original Native actor type readback", "capture/evidence.jsonl"),
        "kin.position": ("runner.py", "original Native pedestrian pose per frame", "native_samples.jsonl"),
        "kin.heading": ("runner.py", "original Native pedestrian forward vector per frame", "native_samples.jsonl"),
        "st.crosswalk": ("runner.py", "Native crosswalk identifier and surveyed geometry readback", "crosswalk-context.json, native_samples.jsonl"),
        "rel.occupies": ("finalize.py", "joined full-footprint occupancy of surveyed crosswalk", "native_samples.jsonl, crosswalk-context.json"),
        "native_pedestrian_pose": ("runner.py", "Native pose, footprint and controller request per frame", "native_samples.jsonl, capture/evidence.jsonl"),
        "camera_frame_join": ("finalize.py", "four source cameras joined to Native frame/time", "video_frames.jsonl, four source .mkv files"),
    }
    for entry in manifest["cases"]:
        construction = json.loads((HERE / entry["construction"]).read_text())
        config = json.loads(next(x["content"] for x in construction["files"] if x["path"] == "config.json"))
        required = set(config["required_atoms"]) | {x["name"] for x in construction["recording_description"]["channels"]}
        if required != set(sources):
            raise ValueError("Crosswalk acquisition contract changed")
        entry["acquisition"] = {name: {"entrypoint": sources[name][0], "method": sources[name][1],
                                       "evidence": sources[name][2]} for name in sorted(required)}
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"selected_cases": len(manifest["cases"]),
                      "acquisition_terms_per_case": len(sources),
                      "manifest_sha256": sha(path)}))


if __name__ == "__main__":
    main()
