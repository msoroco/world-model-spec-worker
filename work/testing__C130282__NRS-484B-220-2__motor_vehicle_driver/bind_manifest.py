"""Bind each exact island case to current selected CPU proof receipts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((ROOT / "execution-manifest.draft.json").read_text(encoding="utf-8"))
    physical_manifest = json.loads((ROOT / "execution-manifest.json").read_text(encoding="utf-8"))
    physical = {entry["case_id"]: entry["physical_preparation"] for entry in physical_manifest["cases"]}
    offline = {(row["case_id"], row["candidate"]): row for row in
               json.loads((ROOT / "cpu-offline-proofs.json").read_text(encoding="utf-8"))}
    compat = {(row["case_id"], row["candidate"]): row for row in
              json.loads((ROOT / "cpu-compatibility-proofs.json").read_text(encoding="utf-8"))}
    delivery = {row["case_id"]: row for row in
                json.loads((ROOT / "cpu-delivery-proofs.json").read_text(encoding="utf-8"))}
    saved = {(row["case_id"], row["variant"]): row for row in
             json.loads((ROOT / "cpu-saved-proofs.json").read_text(encoding="utf-8"))}
    script = ROOT / "delivery_audit.py"
    for entry in manifest["cases"]:
        cid = entry["case_id"]
        entry["physical_preparation"] = physical[cid]
        for candidate in ("primary", "fallback1"):
            selected = entry if candidate == "primary" else entry["candidates"][0]
            off, comp = offline[(cid, candidate)], compat[(cid, candidate)]
            if (off["exit_code"] or comp["exit_code"] or
                    off["construction_sha256"] != selected["construction_sha256"] or
                    comp["construction_sha256"] != selected["construction_sha256"]):
                raise ValueError("stale selected CPU proof: " + cid + " " + candidate)
            selected["offline"] = {"command": off["command"],
                "construction_sha256": selected["construction_sha256"],
                "diagnostic_only": True, "exit_code": 0,
                "log": off["log"], "log_sha256": off["log_sha256"]}
            selected["compatibility"] = {"command": comp["command"],
                "diagnostic_only": True, "receipt": comp["receipt"],
                "sha256": comp["receipt_sha256"], "log": comp["positive_log"],
                "negative_log": comp["negative_log"]}
            if candidate == "primary":
                entry["negative"] = {"diagnostic_only": True,
                                     "log": comp["negative_log"]}
        proof = delivery[cid]
        if proof["positive_exit_code"] or not proof["negative_exit_code"]:
            raise ValueError("independent delivery proof failed: " + cid)
        entry["delivery_acceptance"] = {"case_id": cid, "sets": ["full-test"],
            "checks": ["native_source", "all_participants", "time_join", "full_video_decode",
                       "actual_pixels", "physical_completion"],
            "script": script.name, "script_sha256": sha(script),
            "command": proof["positive_command"],
            "negative_command": proof["negative_command"],
            "test_exit_code": 0, "negative_exit_code": proof["negative_exit_code"],
            "test_log": proof["positive_log"],
            "test_log_sha256": proof["positive_log_sha256"],
            "negative_log": proof["negative_log"],
            "negative_log_sha256": proof["negative_log_sha256"],
            "negative_expected_error": proof["negative_expected_error"],
            "positive_receipt": proof["positive_receipt"],
            "positive_receipt_sha256": proof["positive_receipt_sha256"],
            "diagnostic_only": True, "physical_acceptance": False}
        positive, negative = saved[(cid, "positive")], saved[(cid, "missing-map")]
        if (positive["exit_code"] or positive["missing_evidence"] or
                negative["exit_code"] or not negative["missing_evidence"] or
                not positive["originals_preserved"] or not negative["originals_preserved"]):
            raise ValueError("saved-only source proof incomplete: " + cid)
        entry["post_capture"] = {"command": positive["command"],
            "feedback_command": negative["command"], "recorded_only": True,
            "diagnostic_fixture": True, "physical_acceptance_claimed": False,
            "test_exit_code": 0, "test_log": positive["log"],
            "test_log_sha256": positive["log_sha256"],
            "feedback_test_exit_code": 0, "feedback_log": negative["log"],
            "feedback_log_sha256": negative["log_sha256"]}
    manifest.update({"status": "source-gated-selected-CPU-proofs",
        "diagnostic_only": True, "physical_acceptance": False, "legal_verdict": None})
    (ROOT / "execution-manifest.json").write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(len(manifest["cases"]), "exact island cases bound")


if __name__ == "__main__":
    main()
