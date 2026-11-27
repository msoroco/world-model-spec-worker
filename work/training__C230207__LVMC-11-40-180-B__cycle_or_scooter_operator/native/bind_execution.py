"""Bind the two exact selected signed-road constructions and CPU contracts."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent.parent
REPO = HERE.parents[1]
AID = HERE.name


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def build():
    drafts = json.loads((HERE / "construction-draft.json").read_text())["cases"]
    plan = json.loads((HERE / "case-plan.json").read_text())
    disposition = plan["requirement_dispositions"][0]
    cases = []
    for draft in drafts:
        case = draft["case_id"]
        suffix = case.rsplit("__", 1)[-1]
        construction = HERE / draft["construction"]
        offline_log = "native/cpu-offline-" + suffix + ".log"
        receipt = "physical/" + suffix + "/physical-preparation.json"
        contract_name = "measurement-" + suffix + ".json"
        put(HERE / contract_name, {"format": "worker-measurement-contract",
            "case_id": case, "requirements": [{
                "disposition_index": 0,
                "requirement": disposition["requirement"],
                "source": disposition["source"], "method": "finalize",
                "output_key": "signed_roadway_riding", "value_type": "number",
                "kind": "measured",
                "inputs": ["setup.json", "raw-frames.json", "video_frames.jsonl"]}],
            "negative": {"remove": ["setup.json"],
                         "error_contains": "Missing required source: setup.json"}})
        cases.append({"case_id": case, "kind": "delivery",
            "construction": draft["construction"],
            "construction_sha256": digest(construction),
            "candidate_risk": {"status": "none",
                               "reason": "No observed original Native sign or riding failure yet; reviewed survey controls primary build."},
            "candidates": [], "delivery_readiness": "incomplete",
            "offline": {"command": ".venv-cpu/bin/python runtime.py offline --manifest work/" +
                        AID + "/construction-draft.json --case " + case +
                        " --output .runtime-work/c230207-offline-v3-" + suffix,
                        "exit_code": 0, "construction_sha256": digest(construction),
                        "log": offline_log, "log_sha256": digest(HERE / offline_log)},
            "physical_preparation": {"receipt": receipt,
                                     "sha256": digest(HERE / receipt)},
            "measurement_contract": contract_name,
            "measurement_procedure": {"entrypoint": "finalize.py",
                                      "output_schema": "c230207-signed-access-analysis-v1"},
            "native_handoff": {"python_env_var": "CARLA_PYTHON",
                               "host_env_var": "CARLA_HOST",
                               "port_env_var": "CARLA_PORT"},
            "fixture_recipe": "work/" + AID + "/fixture-" + suffix + ".json"})
    put(HERE / "execution-manifest.json", {
        "format": "worker-execution-manifest", "assignment_id": AID,
        "runtime_manifest_sha256": digest(REPO / "runtime/SOURCE-MANIFEST.json"),
        "status": "partial", "cases": cases})
    print(json.dumps({"case_count": len(cases),
                      "manifest_sha256": digest(HERE / "execution-manifest.json")}))


if __name__ == "__main__":
    build()
