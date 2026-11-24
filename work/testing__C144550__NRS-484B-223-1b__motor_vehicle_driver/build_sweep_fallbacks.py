"""Author one slower-speed physical fallback for each selected sweep point."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    built = []
    for entry in manifest["cases"]:
        suffix = entry["case_id"].split("__")[-1]
        if "pending-" not in suffix:
            continue
        construction = json.loads((HERE / entry["construction"]).read_text())
        config_file = next(f for f in construction["files"] if f["path"] == "config.json")
        config = json.loads(config_file["content"])
        if "target_speed_mps" in config:
            raise ValueError("Sweep primary already overrides target speed")
        config["target_speed_mps"] = 4.2
        config_file["content"] = json.dumps(config, indent=2) + "\n"
        config_file["source"] = None
        path = HERE / "sweep-cases" / suffix / "fallback1-construction.json"
        path.write_text(json.dumps(construction, separators=(",", ":")) + "\n")
        if path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("Fallback construction exceeds return limit")
        entry["candidates"] = [{
            "id": "fallback1",
            "construction": str(path.relative_to(HERE)),
            "construction_sha256": sha(path),
            "trigger": {
                "source": "original ego body and speed history",
                "metric": "completed lane transition within 900 frames without target collision",
                "failure_condition": "primary speed causes off-route or collision interruption before completed lane transition",
            },
            "changed_knobs": ["ego target speed from 5.0 to 4.2 m/s"],
            "status": "authored_cpu_fallback_pending_proof",
        }]
        built.append(entry["case_id"])
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"sweep_fallbacks_authored": built}))


if __name__ == "__main__":
    main()
