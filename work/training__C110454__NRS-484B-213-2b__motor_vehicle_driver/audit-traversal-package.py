"""Independent audit of eight exact C110454 traversal CPU bundles and receipts."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT / "runtime/pipeline/scenario_pipeline"))
from worker_exchange.candidate_constructions import validate
from worker_exchange.measurement_contract import validate as validate_contract

CASES=("traversal_reference","traversal_contrast")
CANDIDATES=("primary","fallback1","fallback2","fallback3")
TRIGGER_NAMES={"fallback1":"max_route_cross_track_error_m",
               "fallback2":"parking_endpoint_speed_m_s",
               "fallback3":"min_ego_pixel_margin_px"}


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest_path=HERE / "draft-traversal-execution-manifest.json"
    manifest=json.loads(manifest_path.read_text())
    batch=json.loads((ROOT / "batch.json").read_text())
    if manifest["runtime_manifest_sha256"]!=batch["runtime"]["source_manifest_sha256"]:
        raise ValueError("Pinned runtime differs")
    plan=json.loads((HERE / "case-plan.json").read_text())
    entries=manifest["cases"]
    if [e["case_id"].split("__")[-1] for e in entries]!=list(CASES):
        raise ValueError("Controlled traversal pair differs")
    comparison=next(c for c in plan["comparisons"] if c["comparison_id"]==HERE.name+"__comparison_traversal")
    if comparison["case_ids"]!=[e["case_id"] for e in entries]:
        raise ValueError("Controlled comparison IDs differ")
    source_path=HERE / "traversal-cpu/trigger-source.json"
    summary_path=HERE / "traversal-cpu/trigger-summary.json"
    source=json.loads(source_path.read_text());summary=json.loads(summary_path.read_text())
    if summary["source_sha256"]!=sha(source_path) or source["source_kind"]!="synthetic_cpu_measurement_fixture":
        raise ValueError("Measured trigger source differs")
    if source["original_native_observed"] is not False or summary["original_pixels_observed"] is not False:
        raise ValueError("Synthetic trigger claims physical observation")
    if len(source["measurements"])!=8 or len(summary["decisions"])!=8:
        raise ValueError("Measured trigger rows missing")
    for raw,decision in zip(source["measurements"],summary["decisions"]):
        route=raw["route_xy_m"];observed=raw["observed_xy_m"]
        left,top,right,bottom=raw["ego_bbox_px"]
        values={"max_route_cross_track_error_m":math.dist(route,observed),
                "parking_endpoint_speed_m_s":raw["parking_endpoint_speed_m_s"],
                "min_ego_pixel_margin_px":min(left,top,1920-right,1080-bottom)}
        if any(abs(values[k]-decision["metrics"][k])>1e-10 for k in values):
            raise ValueError("Measured trigger metric differs")
        expected=(values["max_route_cross_track_error_m"]>.45,
                  values["parking_endpoint_speed_m_s"]>.3,
                  values["min_ego_pixel_margin_px"]<40)
        if tuple(decision[f"fallback{i}_trigger"] for i in (1,2,3))!=expected:
            raise ValueError("Fallback threshold decision differs")
    rows=[];held={c:[] for c in CANDIDATES}
    for entry in entries:
        suffix=entry["case_id"].split("__")[-1]
        validate(HERE,entry,"NRS-484B-213-2b","C110454",required=False,
                 require_alternate=True,candidate_count=4)
        contract=json.loads((HERE / entry["measurement_contract"]).read_text())
        for candidate in CANDIDATES:
            chosen=entry if candidate=="primary" else next(c for c in entry["candidates"] if c["id"]==candidate)
            path=HERE / chosen["construction"];folder=path.parent
            if sha(path)!=chosen["construction_sha256"]:
                raise ValueError("Exact construction hash differs")
            construction=json.loads(path.read_text())
            files={f["path"]:f["content"] for f in construction["files"]}
            cfg=json.loads(files["config.json"])
            if cfg["case_id"]!=entry["case_id"] or cfg["status"]!="unselected_native_runner_prototype":
                raise ValueError("Exact unselected case identity differs")
            if "observed_speed=observed_speed_mps(ego)" not in files["runner_base.py"]:
                raise ValueError("Native body speed not saved after tick")
            if "base.route = traversal_route" not in files["runner.py"] or "def measure_traversal" not in files["finalize.py"]:
                raise ValueError("Traversal runner/finalizer missing")
            validate_contract(contract,plan["requirement_dispositions"],files["finalize.py"],entry["case_id"])
            if candidate!="primary" and chosen["trigger"]["metric"]!=TRIGGER_NAMES[candidate]:
                raise ValueError("Distinct fallback trigger differs")
            held[candidate].append({k:cfg[k] for k in ("cell_id","law_id","actor","duration_s","rate_hz",
                "source_packets","mandatory_channels","recording_description","cameras","engineering_knobs")})
            offline=json.loads((folder / "command-offline.log").read_text())
            if not offline["offline_passed"] or offline["simulation_started"] is not False or offline["case_id"]!=entry["case_id"] or offline["candidate_id"]!=candidate:
                raise ValueError("Pinned exact offline receipt differs")
            if "Ran 7 tests" not in (folder / "offline.log").read_text() or not (folder / "offline.log").read_text().rstrip().endswith("OK"):
                raise ValueError("Exact offline unit tests incomplete")
            receipt=json.loads((folder / "diagnostic-compatibility.json").read_text())
            if receipt["format"]!="worker-package-compatibility-v1" or not receipt["passed"] or receipt["construction_sha256"]!=chosen["construction_sha256"] or receipt["case_id"]!=entry["case_id"] or receipt["candidate_id"]!=candidate:
                raise ValueError("Pinned exact package receipt differs")
            required={"actual_analysis","native_validation","mandatory_observations",
                      "lean_decoder","render","final_decode","acquisition_unchanged"}
            if not required<=set(receipt["checks"]):
                raise ValueError("Package processing stages incomplete")
            analysis_path=folder / "analysis-compatibility.log"
            if sha(analysis_path)!=receipt["log_sha256"]:
                raise ValueError("Saved analysis hash differs")
            analysis=json.loads(analysis_path.read_text())
            relation=analysis["measurements"]["intersection_traversal"]["value"]
            left=0 if suffix=="traversal_reference" else 39
            if relation["moving_traversal_frames"]!=39 or relation["moving_left_traversal_frames"]!=left or analysis["original_joins"]["frames"]!=480 or any(n!=480 for n in analysis["video_frames"].values()):
                raise ValueError("Saved full-body traversal relation differs")
            if "Missing required source: native_samples.jsonl" not in (folder / "negative-analysis.log").read_text():
                raise ValueError("Missing-source negative not observed")
            rows.append({"case_id":entry["case_id"],"candidate":candidate,
                "construction_sha256":chosen["construction_sha256"],
                "receipt_sha256":sha(folder / "diagnostic-compatibility.json"),
                "saved_analysis_sha256":sha(analysis_path),
                "negative_sha256":sha(folder / "negative-analysis.log")})
    for candidate,pair in held.items():
        if pair[0]!=pair[1]:raise ValueError("Controlled held settings differ: "+candidate)
    if len(rows)!=8 or len({r["construction_sha256"] for r in rows})!=8:
        raise ValueError("Eight distinct exact traversal bundles required")
    return {"format":"c110454-independent-traversal-package-audit-v1","passed":True,
        "candidate_count":8,"manifest_sha256":sha(manifest_path),
        "trigger_summary_sha256":sha(summary_path),"rows":rows,
        "scope":"exact offline and synthetic v1 package proofs; original Native/selected strict v2 unproved"}


if __name__=="__main__":print(json.dumps(main(),indent=2))
