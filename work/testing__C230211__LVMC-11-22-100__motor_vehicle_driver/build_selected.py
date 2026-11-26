"""Build seven immutable exact-case Native bundles and risk alternatives."""

import hashlib
import json
from pathlib import Path

from package_spec import AID, ACTOR, CAMERAS, CELL, LAW, RECORDING

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCES = ("runner.py", "analysis.py", "pavement_capture.py",
           "pavement_native.py", "pavement_protection.py", "package_spec.py")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("returned exact bundle exceeds 2 MiB")


def construction(case, ids, speed_scale):
    config = {"assignment_id": AID, "law_id": LAW, "cell_id": CELL,
              "actor": ACTOR, "selected_case_id": case["case_id"],
              "rate_hz": 20, "duration_s": 45,
              "required_atoms": [], "source_packets": [],
              "cameras": CAMERAS, "supported_case_ids": ids,
              "control_profile": {"speed_scale": speed_scale},
              "case": {**case, "recording_description": RECORDING}}
    files = [{"path": name, "content": (HERE / name).read_text()}
             for name in SOURCES]
    files.append({"path": "config.json",
                  "content": json.dumps(config, indent=2, ensure_ascii=False) + "\n"})
    files.append({"path": "tests/test_bundle.py",
                  "content": (HERE / "bundle_test.py").read_text()})
    return {"law_id": LAW, "cell_id": CELL, "actor": ACTOR,
            "case_id": case["case_id"], "entrypoint": "runner.py",
            "recording_description": RECORDING,
            "measurement_plan": {"rate_hz": 20, "duration_s": 45,
                                 "required_channels": [c["name"] for c in RECORDING["channels"]]},
            "static_checks": ["exact source and case identity",
                              "reviewed Native map/pavement/warning/route/work sources",
                              "900 original frames and four synchronized cameras"],
            "termination_rules": ["900 consecutive original 20 Hz Native frames",
                                  "brake, destroy actors and restore world on every exit"],
            "mechanisms": ["physical barrier/person/sign actor construction",
                           "original source-bound pavement and vehicle crossing",
                           "saved-only measurement and independent delivery audit"],
            "files": files}


def build():
    plan = json.loads((HERE / "case-plan.json").read_text())
    ids = [item["case_id"] for item in plan["cases"]]
    if len(ids) != 7 or len(set(ids)) != 7:
        raise ValueError("seven exact protected-pavement cases required")
    manifest = {"format": "worker-execution-manifest", "assignment_id": AID,
                "status": "selected_bundle_proofs_pending",
                "runtime_manifest_sha256": sha(ROOT / "runtime/SOURCE-MANIFEST.json"),
                "cases": []}
    for index, case in enumerate(plan["cases"]):
        suffix = case["case_id"].removeprefix(AID + "__")
        primary = construction(case, ids, 1.0)
        fallback = construction(case, ids, .75)
        primary_path = HERE / ("construction-selected-" + suffix + ".json")
        fallback_path = HERE / ("construction-fallback1-" + suffix + ".json")
        write(primary_path, primary)
        write(fallback_path, fallback)
        if index == 0:
            write(HERE / "construction.json", primary)
            write(HERE / "config.json", json.loads(next(f["content"] for f in primary["files"]
                                                        if f["path"] == "config.json")))
        requirement_rows = []
        for disposition in plan["requirement_dispositions"]:
            requirement_rows.append({"disposition_index": disposition["disposition_index"],
                                     "requirement": disposition["requirement"],
                                     "source": disposition["source"],
                                     "output_key": RECORDING["channels"][disposition["disposition_index"]]["name"],
                                     "method": "source_sealed_pavement_measurement",
                                     "value_type": "object", "kind": "measured",
                                     "inputs": ["pavement-packet.json",
                                                "original-source-receipt.json",
                                                "trace.jsonl"]})
        contract_path = HERE / "diagnostics" / (suffix + "-measurement-contract.json")
        write(contract_path, {"format": "worker-measurement-contract",
                              "case_id": case["case_id"],
                              "requirements": requirement_rows,
                              "negative": {"remove": ["pavement-packet.json"],
                                           "error_contains": "Missing required source: pavement-packet.json"}})
        manifest["cases"].append({
            "case_id": case["case_id"], "kind": "delivery",
            "construction": primary_path.name,
            "construction_sha256": sha(primary_path),
            "candidate_risk": {"status": "physical",
                               "reason": "Native route, physical warning visibility and 900-frame encounter may differ from planned geometry; slower approach increases observable frames without changing the selected statutory variable."},
            "candidates": [{"id": "fallback1", "construction": fallback_path.name,
                            "construction_sha256": sha(fallback_path),
                            "trigger": {"source": "original 900-frame warning, ego path and four-view audit",
                                        "metric": "realized pavement encounter and warning visibility",
                                        "failure_condition": "original route or warning visibility is not established"},
                            "changed_knobs": ["controller target speed scale: 0.75"]}],
            "measurement_contract": "diagnostics/" + suffix + "-measurement-contract.json",
            "fixture_recipe": "work/" + AID + "/diagnostics/" + suffix + "-recipe.json",
            "measurement_procedure": {"entrypoint": "analysis.py",
                                      "method": "source-sealed original pavement and warning readback"},
            "native_handoff": {"python_env_var": "CARLA_PYTHON",
                               "host_env_var": "CARLA_HOST",
                               "port_env_var": "CARLA_PORT",
                               "reviewed_packet_env_var": "C230211_PAVEMENT_SITE"}})
    write(HERE / "execution-manifest.selected-draft.json", manifest)
    return len(manifest["cases"])


if __name__ == "__main__":
    print("selected exact protected-pavement bundles:", build())
