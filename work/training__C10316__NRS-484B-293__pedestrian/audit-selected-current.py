"""Independently verify selected C10316 offline and diagnostic bindings."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shlex
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "runtime/pipeline/scenario_pipeline"))
from worker_exchange.candidate_constructions import validate  # noqa: E402


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def require(ok: bool, message: str) -> None:
    if not ok:
        raise ValueError(message)


def audit() -> dict:
    manifest_path = HERE / "execution-manifest.json"
    manifest = read(manifest_path)
    offline = read(HERE / "update016-selected-offline-summary.json")
    compat = read(HERE / "update016-selected-compatibility-summary.json")
    require(manifest["format"] == "worker-execution-manifest" and
            manifest["status"] == "partial_selected_cpu_proofs_pending" and
            compat["selected_manifest_sha256"] == sha(manifest_path) and
            offline["original_native_proven"] is False and
            compat["original_native_proven"] is False,
            "Selected manifest or diagnostic proof scope changed")
    cases = {item["case_id"]: item for item in manifest["cases"]}
    require(len(cases) == 2 and set(cases) ==
            {HERE.name + "__reference", HERE.name + "__contrast"},
            "Controlled selected pair differs")
    expected = {(case, candidate) for case in cases for candidate in
                ("primary", "fallback1", "fallback2", "fallback3")}
    for summary in (offline, compat):
        rows = summary["results"]
        require(len(rows) == 8 and
                {(row["case_id"], row["candidate_id"]) for row in rows} == expected,
                "Selected proof matrix omits or duplicates a candidate")
    for entry in cases.values():
        validate(HERE, entry, "NRS-484B-293", "C10316", required=True,
                 require_alternate=True, candidate_count=4)
        for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
            selected = (entry if candidate == "primary" else
                        next(row for row in entry["candidates"]
                             if row["id"] == candidate))
            for summary in (offline, compat):
                row = next(item for item in summary["results"]
                           if item["case_id"] == entry["case_id"] and
                           item["candidate_id"] == candidate)
                require(row["construction_sha256"] == selected["construction_sha256"],
                        "Selected proof binds another construction")
                command = shlex.split(row["command"])
                require(entry["case_id"] in command and candidate in command,
                        "Selected proof command chooses another case or candidate")
            proof = read(HERE / selected["compatibility"]["receipt"])
            negative = HERE / selected["compatibility"]["negative_log"]
            require(proof["passed"] is True and
                    proof["negative_error_contains"] in negative.read_text() and
                    proof["negative_removed"] == "native_samples.jsonl" and
                    proof["scope"] == "diagnostic software compatibility only",
                    "Synthetic diagnostic or removed-source negative differs")
    return {"format": "c10316-selected-current-audit-v1",
            "passed": True, "cases": sorted(cases), "candidate_proofs": len(expected),
            "manifest_sha256": sha(manifest_path),
            "offline_summary_sha256": sha(HERE / "update016-selected-offline-summary.json"),
            "compatibility_summary_sha256": sha(HERE / "update016-selected-compatibility-summary.json"),
            "original_native_proven": False,
            "saved_processing_current_manifest_proven": False,
            "physical_or_legal_acceptance": False}


if __name__ == "__main__":
    result = audit()
    (HERE / "update016-selected-current-audit.json").write_text(
        json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
