"""Prepare paired source-bound timing alternatives without physical claims."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    manifest_path = FOLDER / "selected-current-runtime-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"][-1]
        primary = json.loads((FOLDER / entry["construction"]).read_text())
        config_file = next(item for item in primary["files"] if item["path"] == "config.json")
        config = json.loads(config_file["content"])
        if config["other_vehicle_speed_mps"] != 2:
            raise ValueError("Primary emergency actor speed changed")
        config["other_vehicle_speed_mps"] = 3
        config_file["content"] = json.dumps(config, indent=2) + "\n"
        primary["status"] = "unselected_timing_fallback_cpu_draft"
        path = FOLDER / "native/selected" / suffix / "fallback1/construction.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(primary, indent=2, sort_keys=True) + "\n")
        entry["candidates"] = [{"id": "fallback1",
                                "construction": str(path.relative_to(FOLDER)),
                                "construction_sha256": sha(path)}]
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return {"manifest_sha256": sha(manifest_path), "fallbacks": 2}


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
