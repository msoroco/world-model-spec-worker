"""Refresh six selected bundles after source/measurement contract changes."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


for suffix in ("a", "b"):
    primary = HERE / f"selected-current-v2-condition_{suffix}-construction.json"
    for candidate in ("primary", "fallback1", "fallback2"):
        tag = f"condition_{suffix}" + ("" if candidate == "primary" else "-" + candidate)
        path = HERE / f"selected-current-v2-{tag}-construction.json"
        construction = json.loads(path.read_text())
        for item in construction["files"]:
            if item["path"] == "case-plan.json":
                item["content"] = (HERE / "case-plan.json").read_text()
            if item["path"] == "config.json":
                config = json.loads(item["content"])
                config["case_plan_sha256"] = sha(HERE / "case-plan.json")
                item["content"] = json.dumps(config, indent=2) + "\n"
            if item["path"] == "finalize.py":
                item["content"] = (HERE / "current-v2-finalize.py").read_text()
        save(path, construction)
        contract_path = HERE / f"current-runtime-v2-{tag}-measurement-contract.json"
        contract = json.loads(contract_path.read_text())
        contract["requirements"] = [
            {"disposition_index": 0, "requirement": "text-0", "source": "NRS 484B.110",
             "output_key": "zone_overlap_frames", "method": "measure_zone_overlap",
             "value_type": "number", "kind": "measured",
             "inputs": ["native-raw-actors.jsonl", "native-map-readback.json"]},
            {"disposition_index": 1, "requirement": "reviewed-scope-0",
             "source": "inputs/planning/focused-coverage-20261016-v1/coverage-witnesses.json",
             "output_key": "zone_setup_readback", "method": "measure_zone_setup",
             "value_type": "object", "kind": "sourced_context",
             "inputs": ["native-map-readback.json"]},
        ]
        contract["status"] = "selected_cpu_measurement_contract"
        save(contract_path, contract)
        manifest_path = HERE / f"selected-current-v2-{tag}-probe-manifest.json"
        manifest = json.loads(manifest_path.read_text())
        entry = manifest["cases"][0]
        entry["construction_sha256"] = sha(primary)
        if candidate != "primary":
            entry["candidates"][0]["construction_sha256"] = sha(path)
        save(manifest_path, manifest)
        print(tag, sha(path), sha(contract_path))
