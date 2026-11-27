"""Bind measured CPU receipts to the selected, source-gated case manifest.

The diagnostic receipts prove software preparation only. Original reviewed
C111329 sources and Native physical delivery are still required.
"""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n")


def bind():
    manifest = load(ROOT / "execution-manifest.draft.json")
    offline = {(p["case_id"], p["candidate_id"]): p
               for p in load(ROOT / "cpu-offline-proofs.json")["proofs"]}
    for entry in manifest["cases"]:
        case = entry["case_id"]
        short = case.split("__")[-1]
        case_dir = ROOT / "cases" / short
        primary = offline[case, "primary"]
        entry["offline"] = {
            "exit_code": 0,
            "construction_sha256": entry["construction_sha256"],
            "command": primary["command"],
            "log": primary["log"],
            "log_sha256": digest(ROOT / primary["log"]),
            "diagnostic_only": True,
        }
        entry["physical_preparation"] = {
            "receipt": f"cases/{short}/physical/receipt.json",
            "sha256": digest(case_dir / "physical/receipt.json"),
            "diagnostic_only": True,
        }
        entry["native_handoff"] = {
            "python_env_var": "CARLA_PYTHON",
            "host_env_var": "CARLA_HOST",
            "port_env_var": "CARLA_PORT",
            "entrypoint": "native_entry.py",
            "source_gate": "reviewed original C111329 site packet and Native capture",
        }
        for cand_id, target in [("primary", entry), ("fallback1", entry["candidates"][0])]:
            proof = offline[case, cand_id]
            receipt = f"cases/{short}/cpu-compat-{cand_id}-receipt.json"
            positive = f"cases/{short}/cpu-compat-{cand_id}-analysis.log"
            negative = f"cases/{short}/cpu-compat-{cand_id}-negative.log"
            target["compatibility"] = {
                "receipt": receipt,
                "sha256": digest(ROOT / receipt),
                "log": positive,
                "negative_log": negative,
                "diagnostic_only": True,
                "command": (f".venv-cpu/bin/python work/{ROOT.name}/run_compat_deterministic.py --manifest work/{ROOT.name}/execution-manifest.json "
                            f"--case {case} --candidate {cand_id} --output .runtime-work/c111329-287-1c-compat-v11-{short}-{cand_id} "
                            "--library runtime/library --validator .runtime-work/c111329-287-1c-decoder/.lake/build/bin/adapterCheck"),
            }
            if cand_id == "primary":
                entry["negative"] = {"log": negative, "diagnostic_only": True}
            if cand_id != "primary":
                target["offline"] = {
                    "exit_code": 0,
                    "construction_sha256": target["construction_sha256"],
                    "command": proof["command"],
                    "log": proof["log"],
                    "log_sha256": digest(ROOT / proof["log"]),
                    "diagnostic_only": True,
                }
        script = "independent_cpu_delivery.py"
        pos_log = f"cases/{short}/cpu-independent-positive.log"
        neg_log = f"cases/{short}/cpu-independent-negative.log"
        entry["delivery_acceptance"] = {
            "case_id": case,
            "sets": ["full-test"],
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion"],
            "diagnostic_only": True,
            "physical_acceptance": False,
            "test_exit_code": 0,
            "negative_exit_code": 1,
            "negative_expected_error": "Missing required source: effective-site-packet.json",
            "script": script,
            "script_sha256": digest(ROOT / script),
            "command": (f".venv-cpu/bin/python work/{ROOT.name}/{script} "
                        f"--case-id {case} --attempt .runtime-work/c111329-287-1c-compat-v11-{short}-primary "
                        f"--output .runtime-work/c111329-287-1c-independent-v9-{short}.json --diagnostic"),
            "negative_command": (f".venv-cpu/bin/python work/{ROOT.name}/{script} "
                                 f"--case-id {case} --attempt .runtime-work/c111329-287-1c-independent-negative-v9-{short} "
                                 f"--output .runtime-work/c111329-287-1c-independent-negative-v9-{short}.json --diagnostic"),
            "test_log": pos_log,
            "test_log_sha256": digest(ROOT / pos_log),
            "negative_log": neg_log,
            "negative_log_sha256": digest(ROOT / neg_log),
            "positive_receipt": f"cases/{short}/cpu-independent-positive.json",
            "positive_receipt_sha256": digest(case_dir / "cpu-independent-positive.json"),
        }
        entry["saved_processing"] = {
            "diagnostic_only": True,
            "recorded_only": True,
            "positive_command": (f".venv-cpu/bin/python runtime.py process-saved --manifest work/{ROOT.name}/execution-manifest.json "
                                 f"--case {case} --attempt .runtime-work/c111329-287-1c-compat-v11-{short}-primary "
                                 f"--output .runtime-work/c111329-287-1c-saved-v9-{short} --library runtime/library "
                                 "--validator .runtime-work/c111329-287-1c-decoder/.lake/build/bin/adapterCheck"),
            "missing_source_command": (f".venv-cpu/bin/python runtime.py process-saved --manifest work/{ROOT.name}/execution-manifest.json "
                                       f"--case {case} --attempt .runtime-work/c111329-287-1c-saved-negative-attempt-v9-{short} "
                                       f"--output .runtime-work/c111329-287-1c-saved-negative-v9-{short} --library runtime/library "
                                       "--validator .runtime-work/c111329-287-1c-decoder/.lake/build/bin/adapterCheck"),
            "positive_receipt": f"cases/{short}/cpu-saved-positive-processing.json",
            "missing_source_receipt": f"cases/{short}/cpu-saved-negative-processing.json",
        }
        entry["original_source_gate"] = {
            "required_at_execution": True,
            "required_packet": "SHA-bound original fixed-cell map, two junctions, highway banks, complete marking survey, two device authority and operation records",
            "required_media": "900 synchronized original frames with four PNG archives and four independently decoded encoded cameras",
            "legal_adjacency": "undetermined",
            "legal_official_status": "undetermined",
            "nrs_484b_290_exception": "undetermined",
            "physical_completion_claimed": False,
        }
        entry["production_original_audit"] = {
            "script": "production_delivery.py",
            "script_sha256": digest(ROOT / "production_delivery.py"),
            "command": (f"PYTHONDONTWRITEBYTECODE=1 TMPDIR=\"$PWD/.runtime-work/c111329-287-1c-production-audit\" SCENARIO_PIPELINE_OUTPUT_ROOT=\"$PWD/.runtime-work/c111329-287-1c-production-audit\" "
                        f".venv-cpu/bin/python work/{ROOT.name}/production_delivery.py "
                        f"--case-id {case} --attempt \"$ORIGINAL_ATTEMPT\" "
                        "--physical-review-ref \"$SEALED_REVIEW_REF\" --output \"$AUDIT_OUTPUT\""),
            "original_sources_required": True,
            "independent_physical_review_required": True,
            "diagnostic_fixture_accepted": False,
            "physical_completion_claimed": False,
        }
        entry["post_capture"] = {
            "recorded_only": True,
            "command": (f".venv-cpu/bin/python runtime.py process-saved --manifest work/{ROOT.name}/execution-manifest.json "
                        f"--case {case} --attempt \"$ATTEMPT\" --output \"$PROCESSED\" "
                        "--library runtime/library --validator \"$LEAN_VALIDATOR\" "
                        "--owner-release-receipt \"$OWNER_RELEASE_RECEIPT\""),
            "feedback_command": (f".venv-cpu/bin/python runtime.py process-saved --manifest work/{ROOT.name}/execution-manifest.json "
                                 f"--case {case} --attempt \"$ATTEMPT\" --output \"$PROCESSED\" "
                                 "--library runtime/library --validator \"$LEAN_VALIDATOR\" "
                                 "--owner-release-receipt \"$OWNER_RELEASE_RECEIPT\""),
            "test_exit_code": 0,
            "test_log": f"cases/{short}/cpu-saved-positive-processing.json",
            "test_log_sha256": digest(case_dir / "cpu-saved-positive-processing.json"),
            "feedback_test_log": f"cases/{short}/cpu-saved-negative-feedback.json",
            "feedback_test_log_sha256": digest(case_dir / "cpu-saved-negative-feedback.json"),
        }
    manifest["format"] = "worker-execution-manifest"
    manifest["status"] = "source_gated_cpu_prepared_original_native_pending"
    manifest["diagnostic_only"] = False
    manifest["physical_acceptance"] = False
    manifest["legal_verdict"] = None
    manifest["comparison_audits"] = {
        "receipt": "cpu-comparison-proofs.json",
        "sha256": digest(ROOT / "cpu-comparison-proofs.json"),
        "diagnostic_only": True,
    }
    script = "production_comparison.py"
    manifest["comparison_audit_protocol"] = {
        "production_original_attempts_required": True,
        "production_script": script,
        "production_script_sha256": digest(ROOT / script),
        "independent_physical_review_required": True,
        "comparison_ids": ["between_intersections_marking", "both_devices_operating"],
        "production_commands": [
            (f"PYTHONDONTWRITEBYTECODE=1 TMPDIR=\"$PWD/.runtime-work/c111329-287-1c-production-audit\" SCENARIO_PIPELINE_OUTPUT_ROOT=\"$PWD/.runtime-work/c111329-287-1c-production-audit\" "
             f".venv-cpu/bin/python work/{ROOT.name}/{script} --comparison-id {comparison_id} "
             "--reference-attempt \"$REFERENCE_ORIGINAL_ATTEMPT\" --variant-attempt \"$VARIANT_ORIGINAL_ATTEMPT\" "
             "--reference-review-ref \"$REFERENCE_SEALED_REVIEW_REF\" "
             "--variant-review-ref \"$VARIANT_SEALED_REVIEW_REF\" "
             "--output \"$COMPARISON_OUTPUT\"")
            for comparison_id in ("between_intersections_marking", "both_devices_operating")],
        "diagnostic_fixture_accepted": False,
        "physical_realization_claimed": False,
        "legal_verdict": None,
    }
    write(ROOT / "execution-manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    selected = bind()
    print(json.dumps({"cases": len(selected["cases"]), "sha256": digest(ROOT / "execution-manifest.json"),
                      "diagnostic_only": True}))
