"""Create distinct exact-case controller fallbacks for missed Native speed targets."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        key = entry["case_id"].removeprefix(HERE.name + "__")
        primary = json.loads((HERE / entry["construction"]).read_text())
        fallback = json.loads(json.dumps(primary))
        runner = next(item for item in fallback["files"]
                      if item["path"] == "rail_native_runner.py")
        old = "throttle = min(.55, max(0.0, .22 + .18 * gap))"
        new = "throttle = min(.52, max(0.0, .22 + .24 * gap))"
        if runner["content"].count(old) != 1:
            raise ValueError("rail controller fallback edit target differs")
        runner["content"] = runner["content"].replace(old, new)
        runner.pop("source", None)
        fallback["mechanisms"].append(
            "Fallback controller response gain 0.24 and throttle cap 0.52; observed speed remains source-measured.")
        path = HERE / "cases" / key / "fallback1-construction.json"
        path.write_text(json.dumps(fallback, indent=2, sort_keys=True) + "\n")
        entry["candidates"] = [{
            "id": "fallback1", "construction": str(path.relative_to(HERE)),
            "construction_sha256": sha(path),
            "trigger": {"source": "original native-rail-frames.json and original-cameras/approach",
                        "metric": "maximum traversal speed mph and complete original frame continuity",
                        "failure_condition": "measured traversal speed differs from selected target by over 0.5 mph or crossing interval is incomplete"},
            "changed_knobs": ["controller speed-gap gain: 0.18 to 0.24",
                              "controller throttle cap: 0.55 to 0.52"]}]
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print("constructed", len(manifest["cases"]), "source-bound fallback controllers")


if __name__ == "__main__":
    main()
