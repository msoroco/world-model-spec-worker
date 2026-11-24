"""Materialize a canonical root package from the selected first construction."""

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
selected = json.loads((ROOT / "selected-v2-manifest.json").read_text())
first = selected["cases"][0]
bundle = json.loads((ROOT / first["construction"]).read_text())
contents = {item["path"]: item["content"] for item in bundle["files"]}
config = json.loads(contents["config.json"])
config["supported_case_ids"] = selected["selected_case_ids"]
for camera in config["cameras"]:
    camera["pose_strategy"] = "Native attached ego view plus original frame identity"
    camera["fov_deg"] = 90
contents["config.json"] = json.dumps(config, indent=2, ensure_ascii=False) + "\n"
returned = []
for relative, content in contents.items():
    if relative == "case-plan.json":
        continue
    path = ROOT / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    returned.append({"path": relative, "source": f"work/{ROOT.name}/{relative}",
                     "content": content})
construction = {
    "status": "root_cpu_prepared_physical_unverified",
    "case_id": first["case_id"],
    "law_id": bundle["law_id"], "cell_id": bundle["cell_id"],
    "actor": bundle["actor"], "entrypoint": "runner.py",
    "files": returned,
    "measurement_plan": {"selected_cases": selected["selected_case_ids"],
                         "contract": first["measurement_contract"]},
    "recording_description": bundle["recording_description"],
    "static_checks": ["selected offline", "selected public compatibility",
                      "selected recorded-only processing", "independent source isolation"],
    "termination_rules": ["600 source frames at 20 Hz", "Native restoration before owner release"],
    "mechanisms": ["Native ego actor controller", "original map lane readback",
                   "four synchronized camera source joins"],
}
(ROOT / "construction.json").write_text(json.dumps(construction, indent=2,
                                                   ensure_ascii=False) + "\n")
print(json.dumps({"root_files": len(returned), "selected_case_count": 2,
                  "physical_acceptance_claimed": False}))
