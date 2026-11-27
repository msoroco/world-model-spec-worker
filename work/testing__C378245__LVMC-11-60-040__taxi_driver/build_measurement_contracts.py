"""Bind each exact taxi case to source-backed measurement methods."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
INPUTS = ["taxi-source-packet.json", "native_frames.json", "activity_review.json",
          "reviewed_site.json", "native_result.json", "stand_designation.json",
          "taxi_licence.json", "other_regulations.json"]


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> None:
    plan = json.loads((ROOT / "case-plan.json").read_text())
    manifest_path = ROOT / "execution-manifest.draft.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["runtime_manifest_sha256"] = sha(ROOT.parents[1] / "runtime/SOURCE-MANIFEST.json")
    for entry in manifest["cases"]:
        case_id = entry["case_id"]
        suffix = case_id.split("__")[-1]
        requirements = []
        for index, disposition in enumerate(plan["requirement_dispositions"]):
            if disposition["status"] != "selected_required" or case_id not in disposition.get("case_ids", []):
                continue
            if index == 0:
                method, key = "measure_stand_context", "taxi_stand_context"
            elif index == 1:
                method, key = "measure_standing_or_parking", "taxi_halt_activity"
            else:
                method, key = "measure_passenger_exception", "taxi_passenger_exception"
            requirements.append({"disposition_index": index,
                                 "requirement": disposition["requirement"],
                                 "source": disposition["source"],
                                 "output_key": key, "method": method,
                                 "kind": "measured", "value_type": "object",
                                 "inputs": INPUTS})
        contract = {"format": "worker-measurement-contract", "requirements": requirements,
                    "negative": {"remove": ["activity_review.json"],
                                 "error_contains": "Missing required source: activity_review.json"}}
        path = ROOT / "cases" / suffix / "measurement-contract.json"
        path.write_text(json.dumps(contract, indent=2, sort_keys=True) + "\n")
        entry["measurement_contract"] = str(path.relative_to(ROOT))
        entry["measurement_procedure"] = {"entrypoint": "analysis.py"}
        entry["fixture_recipe"] = "work/" + ROOT.name + "/cases/" + suffix + "/fixture-recipe.json"
        entry["native_handoff"] = {"python_env_var": "CARLA_PYTHON",
                                   "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"}
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    build()
    print("six exact taxi measurement contracts built")
