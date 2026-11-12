"""Keep unsupported law observation terms out of Core required_atoms.

The terms stay mandatory in the saved recording contract and Native source
readback. This edits only selected work-owned packages; old receipts remain
historical and must be reproved before binding.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
UNSUPPORTED = {"st.alley", "st.driveway_or_alley_entrance"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, obj):
    path.write_text(json.dumps(obj, indent=2) + "\n")


def main():
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    changed = 0
    for entry in manifest["cases"]:
        for candidate in [entry, *entry["candidates"]]:
            path = HERE / candidate["construction"]
            construction = json.loads(path.read_text())
            item = next(x for x in construction["files"] if x["path"] == "config.json")
            config = json.loads(item["content"])
            required = config["required_atoms"]
            if not UNSUPPORTED <= set(required):
                raise ValueError("Expected unsupported Core atoms missing")
            config["required_atoms"] = [x for x in required if x not in UNSUPPORTED]
            if not UNSUPPORTED <= {x["name"] for x in construction["recording_description"]["channels"]}:
                raise ValueError("Law observation terms dropped from recording contract")
            item["content"] = json.dumps(config, indent=2) + "\n"
            save(path, construction)
            candidate["construction_sha256"] = sha(path)
            for stale in ("offline", "compatibility", "negative", "saved_processing", "physical_preparation", "delivery_acceptance"):
                candidate.pop(stale, None)
            changed += 1
        entry.pop("post_capture", None)
    if changed != 8:
        raise ValueError("Expected eight selected candidates")
    manifest["status"] = "partial_selected_cpu_proofs_pending_physical_unverified"
    save(manifest_path, manifest)
    primary = json.loads((HERE / manifest["cases"][0]["construction"]).read_text())
    config = next(x["content"] for x in primary["files"] if x["path"] == "config.json")
    (HERE / "config.json").write_text(config)
    save(HERE / "construction.json", primary)
    print(json.dumps({"selected_cases": 2, "candidate_constructions_rebound": changed,
                      "manifest_sha256": sha(manifest_path),
                      "unsupported_core_atoms_removed": sorted(UNSUPPORTED),
                      "law_observation_channels_preserved": True}))


if __name__ == "__main__":
    main()
