"""Reprove all 80 selected candidates against the final twenty-case manifest.

Each completed candidate has a retained text proof and may be resumed without
rewriting its diagnostic attempt. A partial attempt is reported for repair.
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import importlib.util
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.json"
RUN_ROOT = ROOT / ".runtime-work/c110919-update063-final-selected-matrix"
PROOFS = HERE / "update063-final-selected-proofs"
INDEX = HERE / "update063-final-selected-index.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text())


def main() -> None:
    spec = importlib.util.spec_from_file_location("ten_case_runner", HERE / "run-ten-case-probe.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)
    runner.MANIFEST = MANIFEST
    runner.RUN_ROOT = RUN_ROOT
    runner.PROOFS = PROOFS
    manifest_sha = sha(MANIFEST)
    manifest = load(MANIFEST)
    entries = manifest["cases"]
    if len(entries) != 20 or len({row["case_id"] for row in entries}) != 20:
        raise ValueError("Final selected inventory must have twenty distinct exact cases")
    jobs = []
    for entry in entries:
        if (entry.get("kind") != "delivery" or entry.get("id", "primary") != "primary"
                or [row["id"] for row in entry.get("candidates", [])] !=
                   ["fallback1", "fallback2", "fallback3"]):
            raise ValueError("Final selected primary/fallback contract differs: " + entry["case_id"])
        jobs.append((entry, "primary", entry))
        jobs.extend((entry, row["id"], row) for row in entry["candidates"])

    def one(job):
        entry, candidate_id, candidate = job
        suffix = entry["case_id"].removeprefix(HERE.name + "__")
        proof_path = PROOFS / suffix / candidate_id / "proof.json"
        attempt = RUN_ROOT / manifest_sha[:12] / suffix / candidate_id
        if proof_path.is_file():
            proof = load(proof_path)
            if (proof.get("manifest_sha256") != manifest_sha or
                    proof.get("construction_sha256") != candidate["construction_sha256"] or
                    proof.get("candidate_id") != candidate_id):
                raise ValueError("Existing selected candidate proof differs: " + suffix)
            row = {"case_id": entry["case_id"], "candidate_id": candidate_id,
                   "proof": str(proof_path.relative_to(HERE)), "sha256": sha(proof_path)}
        else:
            if attempt.exists():
                raise ValueError("Incomplete diagnostic attempt needs inspection: " + str(attempt))
            row = runner.task(entry, candidate_id, candidate)
        selection = load(attempt / "compatibility/candidate-selection.json")
        compat = load(attempt / "compatibility/compatibility.json")
        saved = load(attempt / "saved/v0001/processing.json")
        if (selection.get("manifest_sha256") != manifest_sha or
                selection.get("construction_sha256") != candidate["construction_sha256"] or
                selection.get("case_id") != entry["case_id"] or
                selection.get("candidate_id") != candidate_id or
                compat.get("passed") is not True or saved.get("passed") is not True or
                saved.get("originals_preserved") is not True or
                saved.get("physical_acceptance_claimed") is not False or
                saved.get("legal_acceptance_claimed") is not False):
            raise ValueError("Final selected attempt source binding differs: " + suffix)
        return row

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(one, jobs))
    if sha(MANIFEST) != manifest_sha or len(results) != 80 or len({
            (row["case_id"], row["candidate_id"]) for row in results}) != 80:
        raise ValueError("Final selected matrix changed or incomplete")
    index = {"format": "c110919-final-selected-matrix-v1",
             "manifest_sha256": manifest_sha, "cases": 20, "candidates": 80,
             "results": results, "original_native_accepted": False,
             "physical_or_legal_acceptance": False}
    INDEX.write_text(json.dumps(index, indent=2) + "\n")
    print(json.dumps({"cases": 20, "candidates": 80,
                      "index_sha256": sha(INDEX), "original_native_accepted": False}))


if __name__ == "__main__":
    main()
