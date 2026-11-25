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
                            f"--case {case} --candidate {cand_id} --output .runtime-work/c111329-287-1c-compat-v8-{short}-{cand_id} "
                            "--library runtime/library --validator .runtime-work/c214977-decoder/.lake/build/bin/adapterCheck"),
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
                        f"--case-id {case} --attempt .runtime-work/c111329-287-1c-compat-v8-{short}-primary "
                        f"--output .runtime-work/c111329-287-1c-independent-v6-{short}.json --diagnostic"),
            "negative_command": (f".venv-cpu/bin/python work/{ROOT.name}/{script} "
                                 f"--case-id {case} --attempt .runtime-work/c111329-287-1c-independent-negative-v6-{short} "
                                 f"--output .runtime-work/c111329-287-1c-independent-negative-v6-{short}.json --diagnostic"),
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
                                 f"--case {case} --attempt .runtime-work/c111329-287-1c-compat-v8-{short}-primary "
                                 f"--output .runtime-work/c111329-287-1c-saved-v8-{short} --library runtime/library "
                                 "--validator .runtime-work/c214977-decoder/.lake/build/bin/adapterCheck"),
            "missing_source_command": (f".venv-cpu/bin/python runtime.py process-saved --manifest work/{ROOT.name}/execution-manifest.json "
                                       f"--case {case} --attempt .runtime-work/c111329-287-1c-saved-negative-attempt-v8-{short} "
                                       f"--output .runtime-work/c111329-287-1c-saved-negative-v8-{short} --library runtime/library "
                                       "--validator .runtime-work/c214977-decoder/.lake/build/bin/adapterCheck"),
            "positive_receipt": f"cases/{short}/cpu-saved-positive-processing.json",
            "missing_source_receipt": f"cases/{short}/cpu-saved-negative-processing.json",
        }
    manifest["format"] = "worker-execution-manifest"
    manifest["status"] = "source_gated_cpu_prepared_original_native_pending"
    manifest["diagnostic_only"] = True
    manifest["physical_acceptance"] = False
    manifest["legal_verdict"] = None
    manifest["comparison_audits"] = {
        "receipt": "cpu-comparison-proofs.json",
        "sha256": digest(ROOT / "cpu-comparison-proofs.json"),
        "diagnostic_only": True,
    }
    write(ROOT / "execution-manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    selected = bind()
    print(json.dumps({"cases": len(selected["cases"]), "sha256": digest(ROOT / "execution-manifest.json"),
                      "diagnostic_only": True}))
