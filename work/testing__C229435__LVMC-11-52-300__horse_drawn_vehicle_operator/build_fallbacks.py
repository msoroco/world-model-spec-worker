"""Bind one measurable long-capture queue fallback to each exact case."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        primary = json.loads((ROOT / entry["construction"]).read_text())
        fallback = json.loads(json.dumps(primary))
        config_file = next(file for file in fallback["files"] if file["path"] == "config.json")
        config = json.loads(config_file["content"])
        if config["capture_queue_capacity"] != 4:
            raise ValueError("primary bounded camera queue differs")
        config["capture_queue_capacity"] = 16
        config_file["content"] = json.dumps(config, indent=2, ensure_ascii=False) + "\n"
        path = ROOT / "cases" / suffix / "fallback1-construction.json"
        path.write_text(json.dumps(fallback, indent=2, ensure_ascii=False) + "\n")
        entry["candidates"] = [{
            "id": "fallback1", "construction": "cases/" + suffix + "/fallback1-construction.json",
            "construction_sha256": sha(path),
            "trigger": {"source": "native-run-status.json",
                        "metric": "camera_queue_overflow_count",
                        "failure_condition": "more than zero queued original camera frames dropped"},
            "changed_knobs": ["Raise bounded per-view original RGB queue capacity from 4 to 16 frames; retain 20 Hz and four exact camera sizes"],
        }]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
