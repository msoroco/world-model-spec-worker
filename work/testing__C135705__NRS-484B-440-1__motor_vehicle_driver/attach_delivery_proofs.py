"""Bind exact-case saved audit positives/negatives and both comparison proofs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
ERROR="missing or stale original source: standing-body-history.jsonl"


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    path=HERE/"execution-manifest.json";manifest=json.loads(path.read_text())
    probe_root=(ROOT/(HERE/"delivery-probe-root.txt").read_text().strip()).resolve()
    for entry in manifest["cases"]:
        suffix=entry["case_id"].removeprefix(HERE.name+"__")
        folder=HERE/"cases"/suffix
        positive=folder/"delivery-positive.log";negative=folder/"delivery-negative.log"
        if "diagnostic_audit_test_passed" not in positive.read_text() or ERROR not in negative.read_text():
            raise ValueError("delivery positive/negative diagnostic proof missing")
        command=(f"{ROOT}/.venv-cpu/bin/python {HERE}/delivery_probe.py --case {entry['case_id']} "
                 f"--output {probe_root/(suffix+'-positive')}")
        entry["delivery_acceptance"]={"case_id":entry["case_id"],"sets":["full-test"],
            "checks":["native_source","all_participants","time_join","full_video_decode",
                      "actual_pixels","physical_completion"],
            "script":"delivery_audit.py","script_sha256":sha(HERE/"delivery_audit.py"),
            "command":command,"test_exit_code":0,"test_log":f"cases/{suffix}/delivery-positive.log",
            "test_log_sha256":sha(positive),"negative_command":
                f"{ROOT}/.venv-cpu/bin/python {HERE}/delivery_probe.py --case {entry['case_id']} "
                f"--output {probe_root/(suffix+'-negative')} --negative",
            "negative_exit_code":1,"negative_expected_error":ERROR,
            "negative_log":f"cases/{suffix}/delivery-negative.log","negative_log_sha256":sha(negative),
            "scope":"synthetic source-bound CPU audit with full-decoded camera fixtures; live CARLA visibility and physical acceptance remain unverified"}
        entry["proof_status"]="offline_compatibility_delivery_audit_cpu_passed_physical_review_pending"
    pairs=[("passage_width_with_fixed_view","comparison-width-proof.log",
            "passage_clear_view","passage_blocked"),
           ("two_sided_visibility_with_fixed_passage","comparison-sight-proof.log",
            "passage_clear_view","view_occluded_both")]
    manifest["comparison_audit_commands"]=[]
    for ident,log,left,right in pairs:
        source=HERE/log
        if '"status": "cpu_source_audit_passed"' not in source.read_text():
            raise ValueError("comparison diagnostic proof missing: "+ident)
        manifest["comparison_audit_commands"].append({"assignment_id":HERE.name,
            "comparison_id":ident,"command":
                f"{ROOT}/.venv-cpu/bin/python {HERE}/comparison_audit.py {ident} "
                f"{probe_root/(left+'-positive')} {probe_root/(right+'-positive')} --diagnostic-test",
            "test_log":log,"test_log_sha256":sha(source),"test_exit_code":0})
    manifest["status"]="cpu_audits_passed_live_physical_review_pending"
    path.write_text(json.dumps(manifest,indent=2,allow_nan=False)+"\n")
    print("three case audit positive/negative proofs and two comparison proofs attached")


if __name__=="__main__":main()
