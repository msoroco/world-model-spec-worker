"""Author one bounded vehicle-spawn fallback for each new reverse case."""

import hashlib
import json
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
CASES = PACKAGE / "cases"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def build():
    manifest_path = PACKAGE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    changed = 0
    for entry in manifest["cases"]:
        if "crosswalk" in entry["case_id"]:
            continue
        source = PACKAGE / entry["construction"]
        construction = json.loads(source.read_text())
        template = next(row for row in construction["files"] if row["path"].startswith("site_templates/")
                        and row["path"].endswith("_site.json"))
        site = json.loads(template["content"])
        if site["vehicle_blueprint_id"] != "vehicle.audi.tt":
            raise ValueError("Unexpected primary vehicle blueprint")
        site["vehicle_blueprint_id"] = "vehicle.tesla.model3"
        template["content"] = json.dumps(site, indent=2) + "\n"
        suffix = entry["case_id"].split("__")[-1]
        alternate = CASES / (suffix + "-fallback1-construction.json")
        write(alternate, construction)
        candidate = {
            "id": "fallback1", "construction": "cases/" + alternate.name,
            "construction_sha256": sha(alternate),
            "trigger": {"source": "native-run-status.json and capture/manifest.json",
                        "metric": "subject actor spawn and first original frame",
                        "failure_condition": "Primary Audi blueprint unavailable or subject actor spawn fails before first capture frame"},
            "changed_knobs": ["site_templates vehicle_blueprint_id: vehicle.audi.tt -> vehicle.tesla.model3; route, site geometry, cameras and case identity fixed"],
        }
        if entry.get("candidates") and entry["candidates"] != [candidate]:
            raise ValueError("Existing alternative candidates differ: " + suffix)
        entry["candidates"] = [candidate]
        changed += 1
    if changed != 4:
        raise ValueError("Expected four new alternative cases")
    write(manifest_path, manifest)
    print("Authored four exact vehicle-spawn fallback constructions")


if __name__ == "__main__":
    build()
