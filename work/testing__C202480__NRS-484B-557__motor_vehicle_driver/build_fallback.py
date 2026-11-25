"""Author one measured brake-margin fallback for each exact rail case."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    path = HERE / "execution-manifest.json"
    manifest = json.loads(path.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(HERE.name + "__")
        primary = json.loads((HERE / entry["construction"]).read_text())
        fallback = json.loads(json.dumps(primary))
        controller = next(item for item in fallback["files"]
                          if item["path"] == "native_control.py")
        original = controller["content"]
        changed = original.replace("braking_distance + 0.5",
                                   "braking_distance + 1.5").replace(
                                       "brake = 0.75", "brake = 0.85")
        if changed == original or "braking_distance + 0.5" in changed:
            raise ValueError("brake margin implementation source changed")
        controller["content"] = changed
        controller.pop("source", None)
        dest = HERE / "cases" / suffix / "fallback1-construction.json"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(fallback, indent=2) + "\n")
        entry["candidate_risk"] = {
            "status": "physical",
            "reason": "The original stop may overshoot the requested body-to-rail gap or fail to reach zero speed; a longer braking margin can recover that measured failure."}
        previous = next((c for c in entry.get("candidates", [])
                         if c.get("id") == "fallback1"), {})
        if previous.get("construction_sha256") != sha(dest):
            previous = {}
        previous.update({
            "id": "fallback1", "construction": str(dest.relative_to(HERE)),
            "construction_sha256": sha(dest),
            "changed_knobs": [{"name": "brake_onset_margin_m", "primary": 0.5,
                               "fallback": 1.5},
                              {"name": "brake_strength", "primary": 0.75,
                               "fallback": 0.85}],
            "trigger": {
                "source": "rail-stop-packet.json",
                "metric": "saved complete-stop observation and first-stop body-to-nearest-rail gap in feet",
                "failure_condition": "No complete stop or absolute gap error exceeds 0.5 foot"}})
        entry["candidates"] = [previous]
        print(suffix, "fallback1 brake-margin construction", flush=True)
    path.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
