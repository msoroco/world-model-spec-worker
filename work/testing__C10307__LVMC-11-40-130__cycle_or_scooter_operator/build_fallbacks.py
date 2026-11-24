"""Pin same-case camera pose alternatives for rack occlusion diagnosis."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

OWN = Path(__file__).resolve().parent
MANIFEST = OWN / "execution-manifest.json"
OLD = '"reference_corner": ((0.0, 10.0, 6.0), (-20.0, -90.0, 0.0))'
NEW = '"reference_corner": ((0.0, 7.0, 7.0), (-25.0, -90.0, 0.0))'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        short = entry["case_id"].removeprefix(manifest["assignment_id"] + "__")
        primary = json.loads((OWN / entry["construction"]).read_text())
        candidate = json.loads(json.dumps(primary))
        sources = [item for item in candidate["files"] if item["path"] == "native_capture.py"]
        if len(sources) != 1 or sources[0]["content"].count(OLD) != 1:
            raise ValueError("expected original reference camera pose in " + short)
        sources[0]["content"] = sources[0]["content"].replace(OLD, NEW)
        relative = f"cases/{short}/fallback1-construction.json"
        path = OWN / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(candidate, indent=2, ensure_ascii=False) + "\n")
        entry["candidates"] = [{
            "id": "fallback1", "construction": relative,
            "construction_sha256": sha(path),
            "trigger": {"source": "original reference_corner RGB and frame map from the selected primary Native run",
                        "metric": "rack pixels visible and bicycle/rack co-occurrence over original frames",
                        "failure_condition": "rack occluded or outside reference_corner source frames during bicycle approach"},
            "changed_knobs": ["reference_corner camera position from (0,10,6) m to (0,7,7) m and pitch from -20 to -25 degrees"]
        }]
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
