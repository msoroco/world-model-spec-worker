"""Check electric-class evidence in the selected rider construction without inference."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def audit():
    construction = ROOT/"construction.json"
    runner = ROOT/"native/runner.py"
    actor_map = REPO/"runtime/python/carla_sgg/actors.py"
    ontology = REPO/"runtime/ontology/ATOMS.md"
    preflight = ROOT/"electric-asset-local-preflight.json"
    proposal = json.loads(construction.read_text())
    config = json.loads(next(item["content"] for item in proposal["files"]
                             if item["path"] == "config.json"))
    runner_text = runner.read_text()
    actor_text = actor_map.read_text()
    ontology_text = ontology.read_text()
    local = json.loads(preflight.read_text())
    if (config["cell_id"] != "C104538" or config["law_id"] != "LVMC-11-40-080"
            or "'vehicle.bh.crossbike'" not in runner_text):
        raise ValueError("Selected Native bicycle construction differs")
    for atom in ("ru.electric_bicycle", "ru.electric_scooter"):
        if atom not in ontology_text or atom not in runner_text:
            raise ValueError("Electric class source channel missing")
    if "'selected_class': False" not in runner_text:
        raise ValueError("Selected bicycle must leave electric classes unselected")
    if any(token in actor_text for token in
           ("'vehicle.c104538.electric_bicycle'", "'vehicle.c104538.electric_scooter'")):
        raise ValueError("Unexpected assignment electric asset map changed")
    if local["carla_python_available"] or local["electric_assets_selected"]:
        raise ValueError("Local Native asset preflight changed; re-review required")
    return {"format":"c104538-electric-source-audit-v1","passed":True,
            "selected_machine_class":"bicycle",
            "electric_bicycle_selected":False,"electric_scooter_selected":False,
            "electric_blueprint_inventory_checked_live":False,
            "electric_asset_exists_globally_claimed":False,
            "machine_classification_reviewed":False,
            "unresolved_cpu_construction":"Obtain exact class-specific reviewed asset identity, then bind distinct Native runner variants and controlled applicable-sign cases.",
            "source_sha256":{"construction":sha(construction),"native_runner":sha(runner),
                             "actor_map":sha(actor_map),"ontology":sha(ontology),
                             "local_preflight":sha(preflight)}}


if __name__ == "__main__":
    target=ROOT/"electric-source-audit.json"
    target.write_text(json.dumps(audit(),indent=2,sort_keys=True)+"\n")
    print(json.dumps({"audit_sha256":sha(target)},sort_keys=True))
