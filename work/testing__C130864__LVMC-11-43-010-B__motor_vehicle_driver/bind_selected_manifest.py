"""Bind source-gated exact cases to the returned CPU proof receipts."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True,
                               allow_nan=False) + "\n")


def bind():
    manifest = json.loads((ROOT / "execution-manifest.draft.json").read_text())
    offline = {(row["case_id"], row["candidate"]): row for row in
               json.loads((ROOT / "cpu-offline-proofs.json").read_text())}
    compatibility = {(row["case_id"], row["candidate"]): row for row in
        json.loads((ROOT / "cpu-compatibility-proofs.json").read_text())}
    independent = {row["case_id"]: row for row in
        json.loads((ROOT / "cpu-independent-proofs.json").read_text())}
    for entry in manifest["cases"]:
        cid = entry["case_id"]
        for candidate in ("primary", "fallback1"):
            selected = entry if candidate == "primary" else entry["candidates"][0]
            off = offline[(cid, candidate)]
            comp = compatibility[(cid, candidate)]
            if off["exit_code"] or comp["exit_code"] or (
                    off["construction_sha256"] != selected["construction_sha256"] or
                    comp["construction_sha256"] != selected["construction_sha256"]):
                raise ValueError("stale selected case proof: " + cid + " " + candidate)
            selected["offline"] = {"command": off["command"],
                "construction_sha256": selected["construction_sha256"],
                "diagnostic_only": True, "exit_code": 0, "log": off["log"],
                "log_sha256": off["log_sha256"]}
            selected["compatibility"] = {"command": comp["command"],
                "diagnostic_only": True, "receipt": comp["receipt"],
                "sha256": comp["receipt_sha256"], "log": comp["positive_log"],
                "negative_log": comp["negative_log"]}
            if candidate == "primary":
                entry["negative"] = {"diagnostic_only": True,
                    "log": comp["negative_log"]}
        proof = independent[cid]
        if proof["positive_exit_code"] or proof["negative_exit_code"] == 0:
            raise ValueError("independent CPU proof incomplete: " + cid)
        entry["delivery_acceptance"] = {"case_id": cid,
            "checks": ["native_source", "all_participants", "time_join",
                       "full_video_decode", "actual_pixels", "physical_completion"],
            "script": "independent_cpu_delivery.py",
            "script_sha256": _sha(ROOT / "independent_cpu_delivery.py"),
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
            "diagnostic_only": True, "physical_acceptance": False,
            "sets": ["full-test"]}
        entry["native_handoff"] = {"entrypoint": "native_entry.py",
            "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT",
            "python_env_var": "CARLA_PYTHON",
            "source_gate": "reviewed original C130864 roundabout map and route packet"}
    manifest.update({"format": "worker-execution-manifest",
        "status": "source-gated-selected-CPU-proofs", "diagnostic_only": True,
        "physical_acceptance": False, "legal_verdict": None})
    _write(ROOT / "execution-manifest.json", manifest)
    return manifest


if __name__ == "__main__":
    print(json.dumps({"cases": len(bind()["cases"]),
                      "selected": "source-gated"}))
