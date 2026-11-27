"""Create source-bound exact-case draft entries before offline/runtime proofs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    plan=json.loads((HERE/"case-plan.json").read_text())
    runtime=json.loads((ROOT/"batch.json").read_text())["runtime"]["root"]
    entries=[]
    for case in plan["cases"]:
        cid=case["case_id"];suffix=cid.removeprefix(HERE.name+"__")
        folder=HERE/"cases"/suffix
        construction=folder/"construction.json";fallback=folder/"fallback1-construction.json"
        entries.append({"case_id":cid,"kind":"delivery",
            "construction":f"cases/{suffix}/construction.json",
            "construction_sha256":sha(construction),
            "candidate_risk":{"status":"physical","reason":case["physical_risk_assessment"]["risk"]},
            "candidates":[{"id":"fallback1","construction":f"cases/{suffix}/fallback1-construction.json",
                "construction_sha256":sha(fallback),
                "changed_knobs":(["standing body lateral position", "two occluder lateral positions"]
                                 if suffix=="view_occluded_both" else ["standing body lateral position"]),
                "trigger":{"source":"standing-measurement.json",
                    "metric":"original body passage or two-sided sight geometry",
                    "failure_condition":"primary original measurement misses the requested physical contrast"}}],
            "measurement_contract":f"cases/{suffix}/measurement-contract.json",
            "measurement_procedure":{"entrypoint":"analysis.py"},
            "native_handoff":{"python_env_var":"CARLA_PYTHON","host_env_var":"CARLA_HOST","port_env_var":"CARLA_PORT"},
            "acquisition":{"standing_body_xy_m":{"entrypoint":"native_capture.py",
                "evidence":"standing-body-history.jsonl body_vertices_xy_m","method":"original actor body each world tick"},
                "other_vehicle_body_xy_m":{"entrypoint":"native_capture.py",
                "evidence":"passing-body-history.jsonl body_vertices_xy_m","method":"original westbound actor body each world tick"},
                "two_sided_200ft_sight":{"entrypoint":"native_capture.py",
                "evidence":"approach.mkv and reference_corner.mkv plus occluder-body-history.jsonl",
                "method":"two original 60.96 m cameras and actual prop bodies each world tick"},
                "mechanical_failure_attempt":{"entrypoint":"native_capture.py",
                "evidence":"mechanical-attempt-history.jsonl physics disable and brake request",
                "method":"original worker mechanism command joined to standing actor each world tick"}},
            "proof_status":"draft_offline_and_compatibility_pending"})
    manifest={"format":"worker-execution-manifest","assignment_id":HERE.name,
              "runtime_manifest_sha256":sha(ROOT/runtime/"SOURCE-MANIFEST.json"),
              "cases":entries,"comparison_audit_commands":[],
              "status":"draft_offline_and_compatibility_pending"}
    (HERE/"execution-manifest.json").write_text(json.dumps(manifest,indent=2,allow_nan=False)+"\n")
    print(json.dumps({"cases":len(entries),"construction_sha256":[x["construction_sha256"] for x in entries]}))


if __name__=="__main__":main()
