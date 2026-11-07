"""Bind frozen intersection traversal topics to current exact CPU construction."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
LAW="NRS-484B-213-2b"
PROOFS=("draft-traversal-execution-manifest.json",
        "traversal-cpu/proof.json","traversal-cpu/measurement-contract.json",
        "traversal-cpu/trigger-summary.json","traversal-cpu/package-audit.json")


def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    frozen=read(ROOT / "inputs/coverage/branch-sources.json")["laws"][LAW]
    plan=read(HERE / "case-plan.json")
    matrix_path=ROOT / "work/_shared/branch-coverage.json"
    matrix=read(matrix_path)
    review=read(ROOT / "work/_shared/branch-review.json")
    branch=next(b for b in matrix["laws"][LAW]["branches"] if b["branch_id"].startswith("two_way_intersection_traversal__"))
    case_ids=[HERE.name+"__traversal_reference",HERE.name+"__traversal_contrast"]
    comparison_id=HERE.name+"__comparison_traversal"
    if plan["source_law_text"]!=frozen["law"]["text"] or branch["topic_ids"]!=["text-0","text-1"]:
        raise ValueError("Frozen statutory topics differ")
    if branch["assignment_id"]!=HERE.name or branch["status"]!="runnable" or branch["case_ids"]!=case_ids or branch["comparison_ids"]!=[comparison_id]:
        raise ValueError("CPU branch/case mapping differs")
    cases={c["case_id"]:c for c in plan["cases"]}
    comparison=next(c for c in plan["comparisons"] if c["comparison_id"]==comparison_id)
    if comparison["case_ids"]!=case_ids or any(cases[cid]["source_topic_ids"]!=["text-0","text-1"] for cid in case_ids):
        raise ValueError("Controlled pair topics differ")
    if branch["cpu_proofs"]!={name:sha(HERE / name) for name in PROOFS}:
        raise ValueError("CPU proof identity differs")
    if review["coverage_sha256"]!=sha(matrix_path):
        raise ValueError("Matrix review hash differs")
    if read(HERE / "result.json")["status"]!="blocked":
        raise ValueError("Unselected assignment status changed")
    manifest=read(HERE / "draft-traversal-execution-manifest.json")
    if manifest["status"]!="draft_not_selected" or {e["case_id"] for e in manifest["cases"]}!=set(case_ids):
        raise ValueError("Exact traversal manifest differs")
    package=read(HERE / "traversal-cpu/package-audit.json")
    if not package["passed"] or package["candidate_count"]!=8:
        raise ValueError("Eight exact package proofs absent")
    trigger=read(HERE / "traversal-cpu/trigger-summary.json")
    if trigger["original_native_observed"] is not False or len(trigger["decisions"])!=8:
        raise ValueError("Measured synthetic trigger proof differs")
    env=os.environ.copy()
    env["LD_LIBRARY_PATH"]=str(ROOT / ".runtime-work/geos-wheel/shapely.libs")+os.pathsep+env.get("LD_LIBRARY_PATH","")
    for name in ("audit-traversal-cpu.py","audit-traversal-package.py"):
        subprocess.run([sys.executable,str(HERE / name)],cwd=ROOT,env=env,
                       stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,check=True)
    receipt={"passed":True,"law_id":LAW,"branch_id":branch["branch_id"],
        "controlled_cases":case_ids,"exact_offline_bundles":8,
        "synthetic_v1_positive_negative_pairs":8,"synthetic_trigger_rows":8,
        "saved_full_body_left_traversal_frames":[0,39],
        "selected":False,"original_native_or_strict_v2_verified":False,
        "proof_sha256":branch["cpu_proofs"]}
    (HERE / "traversal-cpu/branch-audit.json").write_text(json.dumps(receipt,indent=2)+"\n")
    print(json.dumps(receipt,sort_keys=True))


if __name__=="__main__":main()
