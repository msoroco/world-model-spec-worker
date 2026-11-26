"""Source-bind same-case slower transfer-motion fallback plans."""

import hashlib
import json
from pathlib import Path


folder = Path(__file__).resolve().parents[1]
manifest_path = folder / "execution-manifest.json"
manifest = json.loads(manifest_path.read_text())
for number, entry in enumerate(manifest["cases"], 1):
    primary = json.loads((folder / entry["construction"]).read_text())
    alternate = json.loads(json.dumps(primary))
    runner = next(item for item in alternate["files"] if item["path"] == "runner.py")
    old = "speed=0.8 if 190 <= index <= 225 else 0.0"
    if runner["content"].count(old) != 1:
        raise ValueError("walker motion knob differs from prospective runner")
    runner["content"] = runner["content"].replace(
        old, "speed=0.6 if 190 <= index <= 225 else 0.0")
    alternate["fallback_reason"] = (
        "If independent pixels do not resolve the passenger/cargo transfer, "
        "slower commanded walker motion gives more detail frames; actual motion remains unverified")
    path = folder / "native" / f"probe-{number}-fallback1-construction.json"
    path.write_text(json.dumps(alternate, indent=2) + "\n")
    entry["candidates"] = [{
        "id": "fallback1", "construction": str(path.relative_to(folder)),
        "construction_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "trigger": {"source": "independent original four-camera pixel review",
                    "metric": "reviewed transfer event visible with actor identity and timestamp",
                    "failure_condition": "original source pixels do not resolve transfer actor and event"},
        "changed_knobs": ["walker commanded speed during frames 190-225: 0.8 to 0.6 m/s"]}]
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
print("four same-case, unchanged-recording physical fallback constructions authored")
