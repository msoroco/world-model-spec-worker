"""Bind twelve current selected offline, compatibility and saved chains."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "execution-manifest.json"
NAMES = ("primary", "fallback1", "fallback2", "fallback3")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def require(condition: bool, detail: str) -> None:
    if not condition:
        raise ValueError(detail)


def bind() -> dict:
    manifest = read(MANIFEST)
    offline = read(HERE / "update041-semantic-bound-offline.json")
    matrix = read(HERE / "update041-final-manifest-matrix.json")
    staged_hash = sha(MANIFEST)
    require(offline["manifest_sha256"] == matrix["manifest_sha256"] == staged_hash,
            "Selected proofs bind another staged manifest")
    require(matrix["original_native_proven"] is False and
            matrix["physical_or_legal_acceptance"] is False,
            "Diagnostic matrix claims original or legal acceptance")
    offline_rows = {(r["case_id"], r["candidate_id"]): r for r in offline["results"]}
    matrix_rows = {(r["case_id"], r["candidate_id"]): r for r in matrix["results"]}
    require(set(offline_rows) == set(matrix_rows) and len(matrix_rows) == 12,
            "Twelve exact selected candidates required")
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        for ident in NAMES:
            selected = entry if ident == "primary" else next(
                candidate for candidate in entry["candidates"] if candidate["id"] == ident)
            off, row = offline_rows[(entry["case_id"], ident)], matrix_rows[(entry["case_id"], ident)]
            require(sha(HERE / selected["construction"]) == selected["construction_sha256"] ==
                    off["construction_sha256"] == row["construction_sha256"],
                    "Selected construction changed")
            require(sha(HERE / off["log"]) == off["log_sha256"] and
                    off["offline_passed"] is True and off["simulation_started"] is False,
                    "Offline proof changed")
            for key in ("compatibility_log", "saved_log"):
                require(sha(HERE / row[key]) == row[key + "_sha256"],
                        "Candidate command log changed")
            relative = f"update041-selected-proofs/{suffix}/{ident}"
            base = HERE / relative
            for name, digest in row["proofs"].items():
                require(sha(base / name) == digest, "Candidate receipt changed: " + name)
            selection, receipt, processing = (read(base / name) for name in
                                              ("candidate-selection.json", "compatibility.json", "processing.json"))
            require(selection["manifest_sha256"] == staged_hash and
                    selection["construction_sha256"] == selected["construction_sha256"] and
                    receipt["passed"] is True and
                    receipt["construction_sha256"] == selected["construction_sha256"] and
                    receipt["log_sha256"] == sha(base / "analysis.log") and
                    receipt["negative_log_sha256"] == sha(base / "negative.log") and
                    processing["passed"] is True and
                    processing["recorded_only"] is True and
                    processing["originals_preserved"] is True and
                    processing["missing_evidence"] is False and
                    processing["native_revision"]["construction_sha256"] ==
                    selected["construction_sha256"] and
                    processing["physical_acceptance_claimed"] is False and
                    processing["legal_acceptance_claimed"] is False,
                    "Selected compatibility or saved proof incomplete")
            selected["offline"] = {
                "construction_sha256": selected["construction_sha256"],
                "command": off["command"], "exit_code": 0,
                "log": off["log"], "log_sha256": off["log_sha256"],
            }
            selected["compatibility"] = {
                "receipt": relative + "/compatibility.json",
                "sha256": sha(base / "compatibility.json"),
                "log": relative + "/analysis.log",
                "negative_log": relative + "/negative.log",
            }
            selected["saved_processing"] = {
                "receipt": relative + "/processing.json",
                "sha256": sha(base / "processing.json"),
            }
        entry["negative"] = {"log": f"update041-selected-proofs/{suffix}/primary/negative.log"}
        primary = matrix_rows[(entry["case_id"], "primary")]
        entry["post_capture"] = {
            "recorded_only": True, "command": primary["saved_command"],
            "feedback_command": primary["saved_command"],
            "test_log": primary["saved_log"],
            "test_log_sha256": primary["saved_log_sha256"],
            "test_exit_code": 0,
            "scope": "Synthetic saved-processing diagnostic; original Native feedback unverified",
        }
        entry["preparation_status"] = "selected_cpu_offline_compat_saved_proven_physical_unverified"
    manifest["status"] = "partial_selected_cpu_proofs_bound_physical_unverified"
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
    return {"cases": len(manifest["cases"]), "candidate_proofs": len(matrix_rows),
            "staged_manifest_sha256": staged_hash,
            "bound_manifest_sha256": sha(MANIFEST)}


if __name__ == "__main__":
    print(json.dumps(bind(), indent=2))
