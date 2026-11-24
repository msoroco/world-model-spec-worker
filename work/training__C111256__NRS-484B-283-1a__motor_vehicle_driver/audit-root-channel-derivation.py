"""Prove all root mandatory channels derive from retained sources only."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / ".runtime-work/c111256-current"
SOURCE = SCRATCH / "witness_1-primary/compat"
FILES = ("trace.jsonl", "capture/evidence.jsonl", "video_frames.jsonl",
         "native_samples.jsonl", "body_history.jsonl", "capture/manifest.json",
         "road_geometry.json")
DERIVED = ("dev.inoperative", "drv.time_to_conflict", "drv.turning", "kin.speed",
           "rel.occupies", "ru.pedestrian", "st.lane_direction")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    spec = importlib.util.spec_from_file_location("root_finalize", HERE / "finalize.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    construction = json.loads((HERE / "construction.json").read_text())
    config = json.loads((HERE / "config.json").read_text())
    inline = {item["path"]: item["content"] for item in construction["files"]}
    if inline["finalize.py"] != (HERE / "finalize.py").read_text() or inline["config.json"] != (HERE / "config.json").read_text():
        raise ValueError("Root materialization differs from source")
    names = {c["name"] for c in config["recording_description"]["channels"]}
    if not set(DERIVED) <= names:
        raise ValueError("Mandatory root derived channels absent")
    with tempfile.TemporaryDirectory(dir=SCRATCH, prefix="root-channels-") as temp:
        attempt = Path(temp)
        for name in FILES:
            source = SOURCE / name
            target = attempt / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        native, mapping, joins = module.joins(attempt, 600)
        geometry = json.loads(module.source(attempt, "road_geometry.json").read_text())
        module.derive_channels(attempt, native, mapping, geometry, config)
        channel_hashes = {}
        for name in DERIVED:
            path = attempt / "channels" / (name + ".jsonl")
            rows = [json.loads(line) for line in path.read_text().splitlines()]
            if len(rows) != 600 or any("value" not in row or "time_s" not in row for row in rows):
                raise ValueError("Derived channel frame count differs: " + name)
            channel_hashes[name] = sha(path)
        native_path = attempt / "native_samples.jsonl"
        native_path.unlink()
        try:
            module.joins(attempt, 600)
        except ValueError as error:
            if "Missing required source: native_samples.jsonl" not in str(error):
                raise
            missing_native = str(error)
        else:
            raise ValueError("Removed Native source was accepted")
        geometry_path = attempt / "road_geometry.json"
        geometry_path.unlink()
        try:
            module.source(attempt, "road_geometry.json")
        except ValueError as error:
            if "Missing required source: road_geometry.json" not in str(error):
                raise
            missing_geometry = str(error)
        else:
            raise ValueError("Removed map source was accepted")
    proof = {"format": "c111256-root-source-channel-proof-v1", "passed": True,
             "finalizer_sha256": sha(HERE / "finalize.py"),
             "construction_sha256": sha(HERE / "construction.json"),
             "config_sha256": sha(HERE / "config.json"),
             "source_sha256": {name: sha(SOURCE / name) for name in FILES},
             "positive_frame_joins": joins["frames"],
             "derived_channel_sha256": channel_hashes,
             "removed_native_error": missing_native,
             "removed_geometry_error": missing_geometry,
             "original_native_or_legal_claimed": False}
    target = HERE / "root-channel-derivation-proof.json"
    target.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"proof_sha256": sha(target), "channels": len(DERIVED),
                      "frames_per_channel": 600, "negative_sources": 2}))


if __name__ == "__main__":
    main()
