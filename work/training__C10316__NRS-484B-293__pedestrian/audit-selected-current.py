"""Independently verify selected C10316 offline and diagnostic bindings."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import shlex
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "runtime/pipeline/scenario_pipeline"))
from worker_exchange.candidate_constructions import validate  # noqa: E402

SOURCE_SPEC = importlib.util.spec_from_file_location(
    "c10316_saved_source_audit", HERE / "audit-update015-saved-evidence.py")
SOURCE_AUDIT = importlib.util.module_from_spec(SOURCE_SPEC)
SOURCE_SPEC.loader.exec_module(SOURCE_AUDIT)


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
    saved = read(HERE / "update017-current-saved-summary.json")
    require(manifest["format"] == "worker-execution-manifest" and
            manifest["status"] == "partial_selected_cpu_proofs_pending" and
            compat["selected_manifest_sha256"] == sha(manifest_path) and
            saved["manifest_sha256"] == sha(manifest_path) and
            offline["original_native_proven"] is False and
            compat["original_native_proven"] is False and
            saved["original_native_proven"] is False and
            saved["physical_or_legal_acceptance"] is False,
            "Selected manifest or diagnostic proof scope changed")
    cases = {item["case_id"]: item for item in manifest["cases"]}
    require(len(cases) == 2 and set(cases) ==
            {HERE.name + "__reference", HERE.name + "__contrast"},
            "Controlled selected pair differs")
    expected = {(case, candidate) for case in cases for candidate in
                ("primary", "fallback1", "fallback2", "fallback3")}
    for summary in (offline, compat, saved):
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
            saved_row = next(item for item in saved["results"]
                             if item["case_id"] == entry["case_id"] and
                             item["candidate_id"] == candidate)
            suffix = entry["case_id"].rsplit("__", 1)[-1]
            target = HERE / "update017-current-proofs" / suffix / candidate
            for name, digest in saved_row["proofs"].items():
                require(sha(target / name) == digest,
                        "Current saved proof file changed: " + name)
            for key in ("compatibility_log", "saved_log"):
                require(sha(HERE / saved_row[key]) == saved_row[key + "_sha256"],
                        "Current saved command log changed: " + key)
            selection = read(target / "candidate-selection.json")
            current_compat = read(target / "compatibility.json")
            processing = read(target / "processing.json")
            require(selection["manifest_sha256"] == sha(manifest_path) and
                    selection["construction_sha256"] == selected["construction_sha256"] and
                    current_compat["passed"] is True and
                    current_compat["construction_sha256"] == selected["construction_sha256"] and
                    current_compat["negative_log_sha256"] == sha(target / "negative.log") and
                    processing["passed"] is True and
                    processing["recorded_only"] is True and
                    processing["originals_preserved"] is True and
                    processing["missing_evidence"] is False and
                    processing["timestamp_joins"] == {
                        "frames": 240, "passed": True,
                        "missing_original_trace_or_map": False} and
                    processing["native_revision"]["construction_sha256"] ==
                    selected["construction_sha256"] and
                    processing["physical_acceptance_claimed"] is False and
                    processing["legal_acceptance_claimed"] is False,
                    "Current saved receipt differs from selected diagnostic contract")
            attempt = ROOT / ".runtime-work" / f"c10316-current-{suffix}-{candidate}-compat"
            source = SOURCE_AUDIT.audit_attempt(attempt)
            for name, digest in source["source_sha256"].items():
                require(processing["original_source_hashes"].get(name) == digest,
                        "Recorded-only processing changed original source: " + name)
            for name in ("overview.mkv", "approach.mkv", "reference_corner.mkv",
                         "driver_reference.mkv", "candidate-selection.json"):
                require(processing["original_source_hashes"].get(name) == sha(attempt / name),
                        "Recorded-only processing changed camera or selection: " + name)
    for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
        reference = ROOT / ".runtime-work" / f"c10316-current-reference-{candidate}-compat"
        contrast = ROOT / ".runtime-work" / f"c10316-current-contrast-{candidate}-compat"
        require((reference / "crosswalk-context.json").read_bytes() ==
                (contrast / "crosswalk-context.json").read_bytes(),
                "Controlled pair changed crosswalk context")
        ref_config, con_config = (read(folder / "config.json") for folder in
                                  (reference, contrast))
        for key in ("cell_id", "law_id", "actor", "duration_s", "rate_hz",
                    "required_atoms", "source_packets", "cameras",
                    "recording_description", "candidate_id"):
            require(ref_config[key] == con_config[key],
                    "Controlled pair changed fixed setting: " + key)
        ref_rows = SOURCE_AUDIT.lines(reference / "native_samples.jsonl")
        con_rows = SOURCE_AUDIT.lines(contrast / "native_samples.jsonl")
        require(len(ref_rows) == len(con_rows) == 240,
                "Controlled pair lacks full original sample window")
        for ref, con in zip(ref_rows, con_rows):
            require(ref["native_frame"] == con["native_frame"] and
                    abs(ref["time_s"] - con["time_s"]) < 1e-9 and
                    abs(ref["pedestrian_xy_m"][0] - con["pedestrian_xy_m"][0]) < 1e-9 and
                    abs(con["pedestrian_xy_m"][1] - ref["pedestrian_xy_m"][1] - 1.3) < 1e-9 and
                    ref["pedestrian_forward_xy"] == con["pedestrian_forward_xy"],
                    "Controlled pair changed more than lateral path position")
    return {"format": "c10316-selected-current-audit-v1",
            "passed": True, "cases": sorted(cases), "candidate_proofs": len(expected),
            "manifest_sha256": sha(manifest_path),
            "offline_summary_sha256": sha(HERE / "update016-selected-offline-summary.json"),
            "compatibility_summary_sha256": sha(HERE / "update016-selected-compatibility-summary.json"),
            "saved_summary_sha256": sha(HERE / "update017-current-saved-summary.json"),
            "current_manifest_saved_proofs": len(expected),
            "controlled_pairs": 4,
            "original_native_proven": False,
            "saved_processing_current_manifest_proven": True,
            "physical_or_legal_acceptance": False}


if __name__ == "__main__":
    result = audit()
    (HERE / "update017-selected-current-audit.json").write_text(
        json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
