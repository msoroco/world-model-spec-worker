"""Independent inventory and retained-source audit of eight diagnostic yield chains."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "draft-yield-branch-execution-manifest.json"
INDEX = HERE / "yield_branch_cases/matrix-index.json"
RUNS = ROOT / ".runtime-work/c110919-update034-yield-full-matrix"
SOURCES = ("native_samples.jsonl", "video_frames.jsonl", "trace.jsonl",
           "capture/evidence.jsonl", "road_geometry.json", "road.xodr",
           "overview.mkv", "approach.mkv", "reference_corner.mkv",
           "driver_reference.mkv")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit(index, manifest):
    require(index["format"] == "c110919-yield-cpu-probe-matrix-v1" and
            index["manifest_sha256"] == sha(MANIFEST) and
            index["cases"] == 2 and index["candidates"] == 8 and
            index["canonical_selected"] is False and
            index["original_native_accepted"] is False,
            "Matrix identity or manifest binding differs")
    expected = {(entry["case_id"], candidate) for entry in manifest["cases"]
                for candidate in ("primary", "fallback1", "fallback2", "fallback3")}
    require(len(index["results"]) == 8 and
            {(row["case_id"], row["candidate_id"]) for row in index["results"]} == expected,
            "Exact candidate inventory incomplete")
    checked = []
    for row in index["results"]:
        entry = next(item for item in manifest["cases"]
                     if item["case_id"] == row["case_id"])
        candidate = row["candidate_id"]
        ref = entry if candidate == "primary" else next(
            item for item in entry["candidates"] if item["id"] == candidate)
        suffix = row["case_id"].removeprefix(HERE.name + "__")
        run = RUNS / suffix / candidate
        proof_path = HERE / row["proof"]
        require(sha(proof_path) == row["sha256"], "Candidate proof hash changed")
        proof = read(proof_path)
        require(proof["case_id"] == row["case_id"] and
                proof["candidate_id"] == candidate and
                proof["manifest_sha256"] == sha(MANIFEST) and
                proof["construction_sha256"] == ref["construction_sha256"] ==
                sha(HERE / ref["construction"]) and
                proof["original_native_accepted"] is False,
                "Candidate construction or proof binding differs")
        for name, rel in (("offline_log_sha256", "offline.log"),
                          ("compatibility_log_sha256", "compatibility.log"),
                          ("process_saved_log_sha256", "process-saved.log")):
            require(proof[name] == sha(proof_path.parent / rel),
                    "Candidate proof log changed")
        compat_path = run / "compatibility/compatibility.json"
        saved_path = run / "saved/v0001/processing.json"
        require(proof["compatibility_receipt_sha256"] == sha(compat_path) and
                proof["saved_receipt_sha256"] == sha(saved_path),
                "Candidate receipt hash changed")
        compat, saved = read(compat_path), read(saved_path)
        require(compat["passed"] is True and saved["passed"] is True and
                compat["construction_sha256"] == ref["construction_sha256"] and
                compat["negative_removed"] == "road_geometry.json" and
                saved["originals_preserved"] is True and
                saved["timestamp_joins"]["passed"] is True and
                saved["physical_acceptance_claimed"] is False and
                saved["legal_acceptance_claimed"] is False,
                "Candidate diagnostic chain or negative failed")
        attempt = run / "compatibility"
        source_hashes = {name: sha(attempt / name) for name in SOURCES}
        require(all(saved["original_source_hashes"].get(name) == digest
                    for name, digest in source_hashes.items()),
                "Retained source differs from saved receipt")
        samples = [json.loads(line) for line in
                   (attempt / "native_samples.jsonl").read_text().splitlines()]
        frames = [json.loads(line) for line in
                  (attempt / "video_frames.jsonl").read_text().splitlines()]
        require(len(samples) == len(frames) == 480 and
                all(sample.get("synthetic_diagnostic") is True and
                    sample.get("speed_provenance") == "synthetic_native_sample" and
                    sample["native_frame"] == frame["native_frame"] and
                    sample["time_s"] == frame["time_s"]
                    for sample, frame in zip(samples, frames)),
                "Diagnostic Native frame or provenance differs")
        checked.append({"case_id": row["case_id"], "candidate_id": candidate,
                        "construction_sha256": ref["construction_sha256"],
                        "source_hashes": source_hashes})
    return checked


def reject(index, manifest):
    try:
        audit(index, manifest)
    except ValueError:
        return True
    raise ValueError("Damaged matrix claim was accepted")


def main():
    manifest, index = read(MANIFEST), read(INDEX)
    checked = audit(index, manifest)
    bad_hash = deepcopy(index)
    bad_hash["results"][0]["sha256"] = "0" * 64
    bad_manifest = deepcopy(index)
    bad_manifest["manifest_sha256"] = "0" * 64
    missing = deepcopy(index)
    missing["results"].pop()
    rejects = {"changed_proof_hash": reject(bad_hash, manifest),
               "wrong_manifest_hash": reject(bad_manifest, manifest),
               "missing_candidate": reject(missing, manifest)}
    result = {"format": "c110919-yield-matrix-audit-v1",
              "manifest_sha256": sha(MANIFEST), "matrix_index_sha256": sha(INDEX),
              "checked": checked, "negative_rejections": rejects,
              "diagnostic_only": True, "original_native_accepted": False}
    path = HERE / "yield_branch_cases/matrix-audit.json"
    path.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"candidate_chains_audited": len(checked),
                      "negative_rejections": sum(rejects.values()),
                      "audit_sha256": sha(path), "original_native_accepted": False}))


if __name__ == "__main__":
    main()
