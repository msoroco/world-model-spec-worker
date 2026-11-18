"""Bind the eight current selected diagnostic chains to the exact manifest."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "execution-manifest.json"
SUMMARY = HERE / "update043c-current-saved-summary.json"
NAMES = ("primary", "fallback1", "fallback2", "fallback3")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def require(condition: bool, detail: str) -> None:
    if not condition:
        raise ValueError(detail)


def bind() -> dict:
    manifest, summary = read(MANIFEST), read(SUMMARY)
    require(summary["manifest_sha256"] == sha(MANIFEST), "Proofs bind another staged manifest")
    require(summary["original_native_proven"] is False and
            summary["physical_or_legal_acceptance"] is False,
            "Selected proofs claim original or legal acceptance")
    rows = {(row["case_id"], row["candidate_id"]): row
            for row in summary["results"]}
    require(len(rows) == 12, "Twelve exact candidate chains required")
    for entry in manifest["cases"]:
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        for ident in NAMES:
            selected = entry if ident == "primary" else next(
                candidate for candidate in entry["candidates"] if candidate["id"] == ident)
            row = rows[(entry["case_id"], ident)]
            require(sha(HERE / selected["construction"]) == selected["construction_sha256"] ==
                    row["construction_sha256"], "Selected construction changed")
            relative = f"update043c-current-proofs/{suffix}/{ident}"
            base = HERE / relative
            for name, digest in row["proofs"].items():
                require(sha(base / name) == digest, "Selected proof file changed: " + name)
            for key in ("offline_log", "compatibility_log", "saved_log"):
                require(sha(HERE / row[key]) == row[key + "_sha256"],
                        "Selected command log changed: " + key)
            selection, receipt, processing = (read(base / name) for name in
                                              ("candidate-selection.json", "compatibility.json", "processing.json"))
            require(selection["manifest_sha256"] == summary["manifest_sha256"] and
                    selection["construction_sha256"] == selected["construction_sha256"] and
                    receipt["passed"] is True and
                    receipt["construction_sha256"] == selected["construction_sha256"] and
                    receipt["log_sha256"] == sha(base / "analysis.log") and
                    receipt["negative_log_sha256"] == sha(base / "negative.log") and
                    processing["passed"] is True and
                    processing["recorded_only"] is True and
                    processing["originals_preserved"] is True and
                    processing["missing_evidence"] is False and
                    processing["native_revision"]["construction_sha256"] == selected["construction_sha256"] and
                    processing["physical_acceptance_claimed"] is False and
                    processing["legal_acceptance_claimed"] is False,
                    "Candidate proof chain incomplete: " + suffix + "/" + ident)
            selected["offline"] = {
                "construction_sha256": selected["construction_sha256"],
                "command": row["offline_command"], "exit_code": 0,
                "log": row["offline_log"], "log_sha256": row["offline_log_sha256"],
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
        entry["negative"] = {"log": f"update043c-current-proofs/{suffix}/primary/negative.log"}
        primary = rows[(entry["case_id"], "primary")]
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
    return {"cases": len(manifest["cases"]), "candidate_proofs": len(rows),
            "staged_manifest_sha256": summary["manifest_sha256"],
            "bound_manifest_sha256": sha(MANIFEST)}


if __name__ == "__main__":
    print(json.dumps(bind(), indent=2))
