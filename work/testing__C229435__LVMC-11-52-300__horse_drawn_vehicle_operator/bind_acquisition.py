"""Bind mandatory observations to original capture and saved-only channel code."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def main():
    path = ROOT / "execution-manifest.json"
    manifest = json.loads(path.read_text())
    for entry in manifest["cases"]:
        construction = json.loads((ROOT / entry["construction"]).read_text())
        entry["acquisition"] = {
            item["name"]: {
                "entrypoint": "night_parking_native.py",
                "method": "run_native with capture_ticks, source sealing, then analysis.finalize",
                "evidence": "original 20 Hz Native body/civil event source plus saved-only channel",
            }
            for item in construction["recording_description"]["channels"]
        }
    path.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
