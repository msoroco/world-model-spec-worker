"""Independently audit eight selected raw-source and saved-processing chains."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "runtime/pipeline/scenario_pipeline"))
from worker_exchange.candidate_constructions import validate  # noqa: E402

SPEC = importlib.util.spec_from_file_location(
    "c10316_raw_source_audit_041", HERE / "audit-update015-saved-evidence.py")
SOURCE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SOURCE)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def require(condition: bool, detail: str) -> None:
    if not condition:
        raise ValueError(detail)


def audit() -> dict:
    manifest = read(HERE / "execution-manifest.json")
    summary = read(HERE / "update041-current-saved-summary.json")
    require(manifest["status"] == "partial_selected_cpu_proofs_bound_physical_unverified" and
            summary["original_native_proven"] is False and
            summary["physical_or_legal_acceptance"] is False,
            "Selected proof scope changed")
    cases = {entry["case_id"]: entry for entry in manifest["cases"]}
    require(set(cases) == {HERE.name + "__reference", HERE.name + "__contrast"},
            "Selected controlled pair differs")
    rows = {(row["case_id"], row["candidate_id"]): row
            for row in summary["results"]}
    require(len(rows) == 8, "Eight selected candidate chains required")
    for entry in cases.values():
        validate(HERE, entry, "NRS-484B-293", "C10316", required=True,
                 require_alternate=True, candidate_count=4)
        suffix = entry["case_id"].rsplit("__", 1)[-1]
        for ident in ("primary", "fallback1", "fallback2", "fallback3"):
            selected = entry if ident == "primary" else next(
                candidate for candidate in entry["candidates"] if candidate["id"] == ident)
            row = rows[(entry["case_id"], ident)]
            base = HERE / "update041-current-proofs" / suffix / ident
            attempt = ROOT / ".runtime-work" / f"c10316-update041-{suffix}-{ident}-compat"
            selection, compat, processing = (read(base / name) for name in
                                             ("candidate-selection.json", "compatibility.json", "processing.json"))
            require(selection["manifest_sha256"] == summary["manifest_sha256"] and
                    selection["construction_sha256"] == selected["construction_sha256"] and
                    compat["passed"] is True and
                    compat["construction_sha256"] == selected["construction_sha256"] and
                    compat["negative_log_sha256"] == sha(base / "negative.log") and
                    compat["negative_error_contains"] in (base / "negative.log").read_text() and
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
                    "Candidate receipt or negative differs: " + suffix + "/" + ident)
            for name, digest in row["proofs"].items():
                require(sha(base / name) == digest, "Copied proof changed: " + name)
            source = SOURCE.audit_attempt(attempt)
            for name, digest in source["source_sha256"].items():
                require(processing["original_source_hashes"].get(name) == digest,
                        "Saved processing changed original source: " + name)
            for name in ("overview.mkv", "approach.mkv", "reference_corner.mkv",
                         "driver_reference.mkv", "candidate-selection.json"):
                require(processing["original_source_hashes"].get(name) == sha(attempt / name),
                        "Saved processing changed source camera or candidate selection")
    for ident in ("primary", "fallback1", "fallback2", "fallback3"):
        ref = ROOT / ".runtime-work" / f"c10316-update041-reference-{ident}-compat"
        con = ROOT / ".runtime-work" / f"c10316-update041-contrast-{ident}-compat"
        require((ref / "crosswalk-context.json").read_bytes() ==
                (con / "crosswalk-context.json").read_bytes(),
                "Controlled pair changed crosswalk context")
        ref_config, con_config = read(ref / "config.json"), read(con / "config.json")
        for key in ("cell_id", "law_id", "actor", "duration_s", "rate_hz",
                    "required_atoms", "source_packets", "cameras", "recording_description",
                    "candidate_id"):
            require(ref_config[key] == con_config[key],
                    "Controlled pair changed fixed setting: " + key)
        reference = SOURCE.lines(ref / "native_samples.jsonl")
        contrast = SOURCE.lines(con / "native_samples.jsonl")
        require(len(reference) == len(contrast) == 240,
                "Controlled pair lacks full source window")
        for left, right in zip(reference, contrast):
            require(left["native_frame"] == right["native_frame"] and
                    abs(left["time_s"] - right["time_s"]) < 1e-9 and
                    abs(left["pedestrian_xy_m"][0] - right["pedestrian_xy_m"][0]) < 1e-9 and
                    abs(right["pedestrian_xy_m"][1] - left["pedestrian_xy_m"][1] - 1.3) < 1e-9 and
                    left["pedestrian_forward_xy"] == right["pedestrian_forward_xy"],
                    "Controlled pair changed more than lateral path")
    return {"format": "c10316-current-source-audit-update041-v1", "passed": True,
            "staged_manifest_sha256": summary["manifest_sha256"],
            "bound_manifest_sha256": sha(HERE / "execution-manifest.json"),
            "cases": sorted(cases), "candidate_proofs": len(rows),
            "controlled_pairs": 4, "original_native_proven": False,
            "physical_or_legal_acceptance": False}


if __name__ == "__main__":
    result = audit()
    (HERE / "update041-current-source-audit.json").write_text(
        json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))
