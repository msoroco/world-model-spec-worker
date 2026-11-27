"""Bind exact source-bound measurement and missing-source contracts."""
import json
from pathlib import Path


FOLDER = Path(__file__).resolve().parent.parent
REPO = FOLDER.parent.parent
manifest_path = FOLDER / "execution-manifest.json"
manifest = json.loads(manifest_path.read_text())
for entry in manifest["cases"]:
    label = entry["case_id"].rsplit("_", 1)[-1]
    path = FOLDER / ("measurement-probe-" + label + ".json")
    contract = {
        "format": "worker-measurement-contract",
        "requirements": [{"disposition_index": 0,
            "requirement": "NRS-484B-769", "source": "NRS 484B.769",
            "output_key": "rider_arm_method_observation",
            "method": "measure_signal_method", "value_type": "object",
            "kind": "measured",
            "inputs": ["rider_arm.jsonl", "camera_frames.jsonl", "road_context.json"]}],
        "negative": {"remove": ["rider_arm.jsonl"],
                     "error_contains": "Missing required source: rider_arm.jsonl"},
    }
    path.write_text(json.dumps(contract, indent=2) + "\n")
    entry["measurement_contract"] = path.relative_to(FOLDER).as_posix()
    entry["fixture_recipe"] = (FOLDER / ("diagnostic-probe-" + label + "-recipe.json")).relative_to(REPO).as_posix()
    entry["acquisition"] = {atom: {
        "entrypoint": "runner.py", "method": "Native articulated rider, full bicycle body, authored road and four synchronized RGB sources",
        "evidence": "Original acquisition and saved source joins; synthetic fixture checks do not prove physical visibility"}
        for atom in ("sig.hand_signal", "ru.subject", "ru.bicycle",
                     "ru.electric_bicycle", "ru.electric_scooter",
                     "st.roadway", "drv.turning")}
manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
print(json.dumps({"exact_measurement_contracts": 3,
                  "negative_removed": "rider_arm.jsonl"}))
