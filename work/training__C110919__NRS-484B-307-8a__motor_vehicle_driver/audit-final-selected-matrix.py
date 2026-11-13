"""Independently audit the final selected candidate receipts and hash bindings."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.json"
INDEX = HERE / "update063-final-selected-index.json"
RUN_ROOT = ROOT / ".runtime-work/c110919-update063-final-selected-matrix"
OUTPUT = HERE / "update063-final-selected-audit.json"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text())


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def check_row(row: dict, expected: dict, manifest_sha: str) -> None:
    cid = expected["case_id"]
    name = expected["candidate_id"]
    suffix = cid.removeprefix(HERE.name + "__")
    require(row["case_id"] == cid and row["candidate_id"] == name,
            "Candidate identity differs")
    proof_file = HERE / row["proof"]
    require(proof_file.resolve().is_relative_to(HERE.resolve()) and
            proof_file.is_file() and digest(proof_file) == row["sha256"],
            "Candidate proof hash differs")
    proof = read(proof_file)
    require(proof["manifest_sha256"] == manifest_sha and
            proof["construction_sha256"] == expected["construction_sha256"] and
            proof["case_id"] == cid and proof["candidate_id"] == name and
            proof["original_native_accepted"] is False,
            "Candidate proof source binding differs")
    run = RUN_ROOT / manifest_sha[:12] / suffix / name
    logs = proof_file.parent
    for key, file in (("offline_log_sha256", logs / "offline.log"),
                      ("compatibility_log_sha256", logs / "compatibility.log"),
                      ("process_saved_log_sha256", logs / "process-saved.log"),
                      ("compatibility_receipt_sha256", run / "compatibility/compatibility.json"),
                      ("saved_receipt_sha256", run / "saved/v0001/processing.json")):
        require(digest(file) == proof[key], "Retained source hash differs: " + key)
    selection = read(run / "compatibility/candidate-selection.json")
    compatible = read(run / "compatibility/compatibility.json")
    saved = read(run / "saved/v0001/processing.json")
    offline = read(logs / "offline.log")
    require(selection["manifest_sha256"] == manifest_sha and
            selection["case_id"] == cid and selection["candidate_id"] == name and
            selection["construction_sha256"] == expected["construction_sha256"] and
            offline["offline_passed"] is True and
            offline["simulation_started"] is False and
            compatible["passed"] is True and
            compatible["negative_removed"] == "road_geometry.json" and
            compatible["construction_sha256"] == expected["construction_sha256"] and
            saved["passed"] is True and saved["recorded_only"] is True and
            saved["originals_preserved"] is True and
            saved["timestamp_joins"]["passed"] is True and
            saved["physical_acceptance_claimed"] is False and
            saved["legal_acceptance_claimed"] is False,
            "Candidate CPU receipt content differs")


def main() -> None:
    manifest_sha = digest(MANIFEST)
    entries = read(MANIFEST)["cases"]
    index = read(INDEX)
    expected = []
    for entry in entries:
        expected.append({"case_id": entry["case_id"], "candidate_id": "primary",
                         "construction_sha256": entry["construction_sha256"]})
        expected.extend({"case_id": entry["case_id"], "candidate_id": c["id"],
                         "construction_sha256": c["construction_sha256"]}
                        for c in entry["candidates"])
    require(len(entries) == 20 and len(expected) == 80 and
            index["manifest_sha256"] == manifest_sha and
            len(index["results"]) == 80 and
            index["original_native_accepted"] is False,
            "Final selected matrix identity differs")
    for row, candidate in zip(index["results"], expected, strict=True):
        check_row(row, candidate, manifest_sha)
    negatives = 0
    for mutation in ("case_id", "candidate_id", "sha256"):
        damaged = copy.deepcopy(index["results"][0])
        damaged[mutation] = "wrong"
        try:
            check_row(damaged, expected[0], manifest_sha)
        except (ValueError, KeyError):
            negatives += 1
    require(negatives == 3, "Candidate identity/hash corruption was not rejected")
    OUTPUT.write_text(json.dumps({"format": "c110919-final-selected-independent-audit-v1",
                                  "manifest_sha256": manifest_sha,
                                  "matrix_sha256": digest(INDEX),
                                  "candidates_checked": 80,
                                  "corruptions_rejected": negatives,
                                  "original_native_accepted": False}, indent=2) + "\n")
    print(json.dumps({"candidates_checked": 80, "corruptions_rejected": negatives,
                      "audit_sha256": digest(OUTPUT)}))


if __name__ == "__main__":
    main()
