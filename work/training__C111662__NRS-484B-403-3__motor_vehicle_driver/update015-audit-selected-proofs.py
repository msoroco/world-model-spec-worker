"""Bind exact selected CPU proof receipts to current manifests and sources."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASES = ("reference", "contrast", "divided_reference", "divided_opening")
CANDIDATES = ("primary", "fallback1", "fallback2", "fallback3")


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def run():
    entries = []
    for case in CASES:
        for candidate in CANDIDATES:
            folder = ROOT / "update015-selected-proof" / case / candidate
            proof_path = folder / "proof.json"
            proof = read(proof_path)
            require(proof["case_id"] == ROOT.name + "__" + case and
                    proof["candidate_id"] == candidate, "Selected proof identity differs")
            manifest = ROOT / proof["manifest"]
            require(sha(manifest) == proof["manifest_sha256"],
                    "Selected manifest hash differs")
            manifest_data = read(manifest)
            entry = next(item for item in manifest_data["cases"]
                         if item["case_id"] == proof["case_id"])
            chosen = entry if candidate == "primary" else next(
                item for item in entry["candidates"] if item["id"] == candidate)
            require(chosen["construction_sha256"] == proof["construction_sha256"]
                    and sha(ROOT / chosen["construction"]) == proof["construction_sha256"],
                    "Selected construction hash differs")
            require(entry["fixture_recipe"] == proof["recipe"] and
                    sha(REPO / proof["recipe"]) == proof["recipe_sha256"],
                    "Selected recipe hash differs")
            for path_key, hash_key in (("offline_log", "offline_log_sha256"),
                                       ("compatibility_receipt", "compatibility_sha256"),
                                       ("negative_log", "negative_log_sha256"),
                                       ("processing_receipt", "processing_sha256")):
                require(sha(ROOT / proof[path_key]) == proof[hash_key],
                        "Selected proof source hash differs: " + path_key)
            compat = read(ROOT / proof["compatibility_receipt"])
            processing = read(ROOT / proof["processing_receipt"])
            require(compat.get("passed") is True and processing.get("passed") is True
                    and compat.get("candidate_id") == candidate and
                    processing.get("candidate_id") == candidate and
                    processing.get("originals_preserved") is True and
                    processing.get("final_video_checks", {}).get("passed") is True,
                    "Selected compatibility or saved processing failed")
            require("Missing required source: raw.json" in
                    (ROOT / proof["negative_log"]).read_text(),
                    "Selected negative source was not rejected")
            entries.append({"case_id": proof["case_id"], "candidate_id": candidate,
                            "proof": str(proof_path.relative_to(ROOT)),
                            "proof_sha256": sha(proof_path),
                            "manifest_sha256": proof["manifest_sha256"],
                            "construction_sha256": proof["construction_sha256"],
                            "recipe_sha256": proof["recipe_sha256"],
                            "offline_passed": True, "compatibility_passed": True,
                            "negative_rejected": True, "saved_processing_passed": True})
    return {"format": "c111662-selected-cpu-proof-matrix-v1",
            "assignment_id": ROOT.name, "candidate_count": len(entries),
            "passed": len(entries) == 16, "entries": entries,
            "scope": "selected synthetic diagnostics, not original Native or physical/legal acceptance"}


if __name__ == "__main__":
    result = run()
    output = ROOT / "update015-selected-all-proof-matrix.json"
    output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"passed": result["passed"], "candidate_count": result["candidate_count"],
                      "sha256": sha(output)}))
