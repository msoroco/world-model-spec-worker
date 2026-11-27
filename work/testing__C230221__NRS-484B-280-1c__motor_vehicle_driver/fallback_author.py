"""Prepare identical paired fallback spawn tuning for a Native occupied spawn."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CASES = ("marked_crosswalk", "unmarked_crosswalk")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for suffix, entry in zip(CASES, manifest["cases"]):
        primary = json.loads((ROOT / entry["construction"]).read_text())
        alternate = json.loads(json.dumps(primary))
        scene_entry = next(item for item in alternate["files"] if item["path"] == "scene.json")
        scene = json.loads(scene_entry["content"])
        scene["ego_start_xy_m"][0] -= 3.0
        scene_entry["content"] = json.dumps(scene, indent=2) + "\n"
        alternate["mechanisms"].append("fallback ego spawn shifted 3 m upstream on the same reviewed road")
        path = ROOT / ("fallback-" + suffix + "-construction.json")
        path.write_text(json.dumps(alternate, indent=2, ensure_ascii=False) + "\n")
        entry["candidate_risk"] = {"status": "physical",
            "reason": "The primary Native ego spawn can be occupied by an ambient vehicle; a same-road upstream spawn is an engineering alternative shared across the pair."}
        prior = next((item for item in entry.get("candidates", []) if item.get("id") == "fallback1"), {})
        candidate = {**prior, "id": "fallback1", "construction": path.name,
                     "construction_sha256": sha(path),
                     "changed_knobs": ["ego_start_xy_m.x: primary -30 m -> fallback -33 m on the same reviewed road"],
                     "trigger": {"source": "Native CARLA ego spawn result and original actor inventory",
                                 "metric": "primary ego spawn availability",
                                 "failure_condition": "primary ego spawn occupied or rejected by the Native world"}}
        if candidate.get("offline", {}).get("construction_sha256") != candidate["construction_sha256"]:
            candidate.pop("offline", None)
            candidate.pop("compatibility", None)
        entry["candidates"] = [candidate]
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
