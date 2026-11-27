"""Bind seven exact construction hashes without fabricating delivery receipts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    plan=json.loads((HERE/"case-plan.json").read_text())
    entries=[]
    for case in plan["cases"]:
        suffix=case["case_id"].rsplit("__",1)[-1]
        relative=f"cases/{suffix}/construction.json"
        entries.append({"case_id":case["case_id"],"kind":"delivery",
                        "construction":relative,
                        "construction_sha256":sha(HERE/relative),
                        "measurement_contract":f"cases/{suffix}/measurement-contract.json",
                        "measurement_procedure":{"entrypoint":"analysis.py"},
                        "candidate_risk":{
                            "status":case["physical_risk_assessment"]["status"],
                            "reason":case["physical_risk_assessment"]["risk"]},
                        "candidates":[],
                        "native_handoff":{"python_env_var":"CARLA_PYTHON",
                                          "host_env_var":"CARLA_HOST",
                                          "port_env_var":"CARLA_PORT"},
                        "proof_status":"offline_and_compatibility_receipts_pending"})
    manifest={"format":"worker-execution-manifest",
              "assignment_id":plan["assignment_id"],
              "runtime_manifest_sha256":sha(REPO/"runtime/SOURCE-MANIFEST.json"),
              "status":"draft_not_delivery_ready","cases":entries}
    (HERE/"execution-manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    print(json.dumps({"exact_cases_bound":len(entries),"delivery_ready_claimed":False}))


if __name__=="__main__":main()
