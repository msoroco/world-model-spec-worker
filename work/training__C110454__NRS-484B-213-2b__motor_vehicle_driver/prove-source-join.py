"""Prove current 32 candidate source joins and original-mode rejection."""
import hashlib
import json
import tempfile
from pathlib import Path

from source_join_audit import SOURCES, audit, sha

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
GROUPS = (
    ("intersection", "draft-execution-manifest.json", "c110454-update015-intersection-matrix-v1"),
    ("statutory", "draft-statutory-execution-manifest.json", "c110454-update015-statutory-matrix-v2"),
    ("traversal", "draft-traversal-execution-manifest.json", "c110454-update015-traversal-matrix-v1"),
)


def rejects(call, expected):
    try:
        call()
    except ValueError as error:
        if expected not in str(error):
            raise AssertionError("Wrong rejection: " + str(error)) from error
    else:
        raise AssertionError("Expected rejection: " + expected)


def main():
    results = []
    first = None
    for group, manifest_name, root_name in GROUPS:
        manifest = json.loads((HERE / manifest_name).read_text())
        for entry in manifest["cases"]:
            case = entry["case_id"]
            suffix = case.rsplit("__", 1)[-1]
            for candidate in [entry, *entry["candidates"]]:
                ident = candidate.get("id", "primary")
                attempt = ROOT / ".runtime-work" / root_name / suffix / ident / "compatibility"
                saved = HERE / f"update015-{group}-proofs" / suffix / ident / "process-saved.json"
                construction = HERE / candidate["construction"]
                assert sha(construction) == candidate["construction_sha256"]
                result = audit(attempt, saved, case, ident, candidate["construction_sha256"],
                               diagnostic=True)
                assert result["joined_frames"] == 480 and result["passed"] is False
                assert result["original_native_sources_verified"] is False
                rejects(lambda: audit(attempt, saved, case, ident,
                                      candidate["construction_sha256"]),
                        "Synthetic source cannot establish original Native delivery")
                if first is None:
                    first = (attempt, saved, case, ident, candidate["construction_sha256"])
                results.append({"case_id": case, "candidate_id": ident,
                                "construction_sha256": candidate["construction_sha256"],
                                "saved_processing_sha256": sha(saved),
                                "joined_frames": 480, "production_rejected": True})
    assert len(results) == 32 and len({r["case_id"] for r in results}) == 8
    attempt, saved, case, ident, construction_sha = first
    with tempfile.TemporaryDirectory() as directory:
        temp = Path(directory)
        for name in SOURCES:
            dst = temp / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            dst.symlink_to((attempt / name).resolve())
        receipt = json.loads(saved.read_text())
        trace = [json.loads(line) for line in (attempt / "trace.jsonl").read_text().splitlines()]
        trace[0]["time_s"] += .1
        changed = temp / "changed-trace.jsonl"
        changed.write_text("".join(json.dumps(row) + "\n" for row in trace))
        (temp / "trace.jsonl").unlink()
        (temp / "trace.jsonl").symlink_to(changed)
        receipt["original_source_hashes"]["trace.jsonl"] = sha(changed)
        changed_receipt = temp / "changed-processing.json"
        changed_receipt.write_text(json.dumps(receipt))
        rejects(lambda: audit(temp, changed_receipt, case, ident, construction_sha,
                              diagnostic=True), "Original frame/time join differs")
        receipt["original_source_hashes"]["trace.jsonl"] = "0"*64
        changed_receipt.write_text(json.dumps(receipt))
        rejects(lambda: audit(temp, changed_receipt, case, ident, construction_sha,
                              diagnostic=True), "Saved source hash differs")
    report = {"format": "c110454-source-join-cpu-proof-v1", "candidate_count": len(results),
              "case_count": 8, "joined_frames": len(results)*480,
              "candidate_results": results,
              "negative_checks": ["synthetic_as_original_all_32", "changed_frame_time",
                                  "stale_saved_source_hash"],
              "original_native_or_delivery_acceptance_claimed": False}
    path = HERE / "update016-source-join-proof.json"
    path.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"candidate_count": len(results), "case_count": 8,
                      "joined_frames": len(results)*480,
                      "negative_checks": report["negative_checks"],
                      "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
