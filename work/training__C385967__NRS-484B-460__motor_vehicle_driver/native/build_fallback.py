"""Freeze distinct service-brake fallback for each exact angle case."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n")


def build():
    draft = json.loads((HERE / "selected-draft-manifest.json").read_text())
    compat = json.loads((FOLDER / "selected-compat-manifest.json").read_text())
    for letter, draft_entry, compat_entry in zip("ab", draft["cases"], compat["cases"]):
        primary = json.loads((HERE / f"selected-{letter}-construction.json").read_text())
        fallback = json.loads(json.dumps(primary))
        item = next(item for item in fallback["files"] if item["path"] == "config.json")
        config = json.loads(item["content"])
        if config.get("parking_brake_mode") != "hand_brake":
            raise ValueError("Unexpected primary brake request")
        config["parking_brake_mode"] = "service_and_hand_brake"
        item["content"] = json.dumps(config, indent=2) + "\n"
        path = HERE / f"selected-{letter}-fallback1-construction.json"
        save(path, fallback)
        candidate = {"id": "fallback1", "construction": path.name,
                     "construction_sha256": sha(path)}
        draft_entry["candidates"] = [candidate]
        compat_entry["candidate_risk"] = {"status": "physical",
            "reason": "Original at-rest speed and body containment may fail with hand brake alone"}
        compat_entry["candidates"] = [{**candidate,
            "construction": "native/" + path.name,
            "trigger": {"source": "original Native native_samples.jsonl",
                        "metric": "maximum at-rest ego_speed_mps",
                        "failure_condition": "original speed exceeds engineering 0.1 m/s diagnostic"},
            "changed_knobs": ["parking_brake_mode"]}]
        print(json.dumps({"case_id": compat_entry["case_id"],
                          "fallback_sha256": candidate["construction_sha256"]}, sort_keys=True))
    save(HERE / "selected-draft-manifest.json", draft)
    save(FOLDER / "selected-compat-manifest.json", compat)


if __name__ == "__main__":
    build()
