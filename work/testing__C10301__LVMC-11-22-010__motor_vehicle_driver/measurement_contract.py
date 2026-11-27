"""Check exact alley measurement contracts against sealed saved sources."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


SOURCE_FILES = {
    "ego": "ego.jsonl",
    "context": "context.jsonl",
    "operation": "operation.jsonl",
    "camera_frame_map": "camera-frame-map.jsonl",
}


def check(contract_path: Path, attempt: Path, measurement: dict) -> dict:
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if contract.get("format") != "worker-measurement-contract":
        raise ValueError("unknown measurement contract")
    case_id = contract.get("case_id")
    if not case_id or measurement.get("case_id") != case_id:
        raise ValueError("exact measurement case mismatch")
    if measurement.get("selected_requirement") != "LVMC-11-22-010":
        raise ValueError("selected statutory requirement mismatch")
    interior = measurement.get("interior_source_audit")
    expected_state = "unresolved" if interior is not None else "unobserved"
    if measurement.get("attention_state") != expected_state or measurement.get("legal_judgment") != "unresolved":
        raise ValueError("unsupported interior attention or legal judgment")
    if interior is not None:
        if (interior.get("case_id") != case_id or interior.get("original_frames") != 900
                or interior.get("legal_judgment") != "unresolved"
                or interior.get("physical_acceptance_claimed") is not False):
            raise ValueError("original interior measurement contract differs")
    if measurement.get("original_frames") != 900 or measurement.get("decoded_original_pngs") != 3600:
        raise ValueError("incomplete original capture window")
    hashes = measurement.get("source_sha256", {})
    for key, name in SOURCE_FILES.items():
        source = attempt / name
        if not source.is_file():
            raise ValueError("Missing required source: " + name)
        if hashlib.sha256(source.read_bytes()).hexdigest() != hashes.get(key):
            raise ValueError("original source hash mismatch: " + name)
    operation = measurement.get("operation_measurement", {})
    if operation.get("frame_count") != 900 or operation.get("case_id") != case_id:
        raise ValueError("operation measurement identity or duration mismatch")
    expected_outputs = {row["output_key"] for row in contract.get("requirements", [])}
    if expected_outputs != {"operation_measurement", "source_sha256", "decoded_original_pngs", "attention_state"}:
        raise ValueError("selected requirement outputs incomplete")
    return {"format": "worker-alley-measurement-contract-check", "case_id": case_id,
            "source_sha256": hashes, "passed": True, "legal_judgment": "unresolved"}
