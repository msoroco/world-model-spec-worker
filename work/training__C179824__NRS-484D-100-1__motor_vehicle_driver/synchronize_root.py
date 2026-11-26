"""Synchronize the canonical root catalogue with selected exact Native cases."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def load(name):
    return json.loads((ROOT / name).read_text())


def save(name, data):
    (ROOT / name).write_text(json.dumps(data, indent=2) + "\n")


manifest = load("execution-manifest.json")
plan = load("case-plan.json")
config = load("config.json")
config["supported_case_ids"] = [item["case_id"] for item in manifest["cases"]]
config["status"] = "selected_cpu_proofs_in_progress"
config["recording_description"] = {
    "channels": [], "context_inputs": [],
    "limitations": ["Original Native capture, independent original pixels and legal disposition are not attested by CPU diagnostics"],
}
names = set()
for entry in manifest["cases"]:
    construction = load(entry["construction"])
    for channel in construction["recording_description"]["channels"]:
        if channel["name"] not in names:
            config["recording_description"]["channels"].append(channel)
            names.add(channel["name"])
for observation in plan["observations"]:
    name = observation["name"]
    if name not in names:
        config["recording_description"]["channels"].append({
            "name": name, "unit": "structured", "sampling_rate_hz": 20,
            "method": "Source-bound exact-case Native acquisition and independent review",
            "time_window": "600 frames", "reference_frame": "Nevada paved roadway",
            "uncertainty": "physical and legal acceptance require original local review",
        })
        names.add(name)
save("config.json", config)

original_mapping = plan["source_observation_mapping"]
if isinstance(original_mapping, list):
    plan["source_observation_mapping"] = {
        item["term"]: {"evidence": item["measurement"], "channels": [item["term"]],
                       "source_refs": item["source_refs"], "status": item["status"]}
        for item in original_mapping
    }
plan["camera_plan"]["coverage"] = [
    {"view": "overview", "subject": "subject vehicle, paved highway and shoulder", "interval": "all 600 frames"},
    {"view": "approach", "subject": "device face, vehicle lamps and travel path", "interval": "all 600 frames"},
    {"view": "reference_corner", "subject": "person and vehicle targets at the selected 1,000-foot boundary", "interval": "all 600 frames"},
    {"view": "driver_reference", "subject": "driver view of targets, roadway and emitted lamps", "interval": "all 600 frames"},
]
save("case-plan.json", plan)

construction = load("construction.json")
construction["entrypoint"] = "runner.py"
construction["recording_description"] = config["recording_description"]
construction["files"] = [{"path": name, "content": (ROOT / name).read_text()}
                         for name in ("runner.py", "config.json", "tests/test_native.py")]
construction["measurement_plan"] = {
    "selected_exact_cases": len(manifest["cases"]),
    "per_case_procedure": "execution-manifest.json binds each source-hashed Native runner and recorded-only finalizer",
    "independent_review": "original four-view pixels, class equipment sufficiency, civil time, discernibility, device authority and parked exception",
    "legal_verdict_claimed": False,
}
construction["status"] = "selected_cpu_proofs_in_progress"
save("construction.json", construction)
print(json.dumps({"supported_cases": len(config["supported_case_ids"]),
                  "root_channels": len(config["recording_description"]["channels"])}))
