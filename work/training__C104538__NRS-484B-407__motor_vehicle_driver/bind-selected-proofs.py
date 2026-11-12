"""Bind already passed exact CPU proofs to the selected manifest.

This script verifies every source hash before changing the manifest. It does not
claim physical preparation or delivery readiness.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAMES = ("primary", "fallback1", "fallback2", "fallback3")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def bind() -> dict:
    manifest_path = HERE / "execution-manifest.json"
    manifest = read(manifest_path)
    proposal_hash = sha(HERE / "proposals/cases.json")
    manifest["selection_review"]["proposal_sha256"] = proposal_hash
    offline = read(HERE / "update016-selected-offline-summary.json")
    rows = {(r["case_id"], r["candidate_id"]): r for r in offline["results"]}
    expected = {(e["case_id"], name) for e in manifest["cases"] for name in NAMES}
    if set(rows) != expected:
        raise ValueError("Offline proof matrix differs from selected matrix")
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        for name in NAMES:
            target = entry if name == "primary" else next(c for c in entry["candidates"] if c["id"] == name)
            row = rows[(entry["case_id"], name)]
            log = HERE / row["log"]
            if (row["construction_sha256"] != target["construction_sha256"] or
                    not row["offline_passed"] or row["simulation_started"] or
                    sha(log) != row["log_sha256"]):
                raise ValueError("Offline proof changed: " + suffix + " " + name)
            target["offline"] = {
                "command": row["command"], "exit_code": 0,
                "construction_sha256": row["construction_sha256"],
                "log": row["log"], "log_sha256": row["log_sha256"],
            }
            proof_dir = HERE / "update016-selected-proofs" / suffix / name
            receipt = proof_dir / "compatibility.json"
            positive = proof_dir / "analysis.log"
            negative = proof_dir / "negative.log"
            result = read(receipt)
            if (result["format"] != "worker-package-compatibility" or
                    result["passed"] is not True or
                    result["case_id"] != entry["case_id"] or
                    result["candidate_id"] != name or
                    result["construction_sha256"] != target["construction_sha256"] or
                    sha(positive) != result["log_sha256"] or
                    sha(negative) != result["negative_log_sha256"]):
                raise ValueError("Compatibility proof changed: " + suffix + " " + name)
            target["compatibility"] = {
                "receipt": str(receipt.relative_to(HERE)),
                "sha256": sha(receipt),
                "log": str(positive.relative_to(HERE)),
                "negative_log": str(negative.relative_to(HERE)),
            }
    manifest["status"] = "partial_selected_cpu_proofs_bound_physical_and_audit_pending"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    return {"cases": len(manifest["cases"]), "candidate_proofs": len(expected),
            "proposal_sha256": proposal_hash, "manifest_sha256": sha(manifest_path),
            "status": manifest["status"]}


if __name__ == "__main__":
    print(json.dumps(bind(), indent=2))
