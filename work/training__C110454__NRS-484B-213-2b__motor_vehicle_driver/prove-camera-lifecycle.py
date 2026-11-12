"""Exercise 32 source-bound camera inventories and strict lifecycle negatives."""
import hashlib
import json
import tempfile
from pathlib import Path

from camera_lifecycle_audit import CAMERAS, HERE, ROOT, audit, check_release
from source_join_audit import SOURCES, sha

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
    cases, candidates, camera_checks = set(), 0, 0
    decoded = {}
    first = None
    for group, manifest_name, root_name in GROUPS:
        manifest = json.loads((HERE / manifest_name).read_text())
        for entry in manifest["cases"]:
            case = entry["case_id"]
            cases.add(case)
            suffix = case.rsplit("__", 1)[-1]
            for candidate in [entry, *entry["candidates"]]:
                ident = candidate.get("id", "primary")
                attempt = ROOT / ".runtime-work" / root_name / suffix / ident / "compatibility"
                saved = HERE / f"update015-{group}-proofs" / suffix / ident / "process-saved.json"
                digest = candidate["construction_sha256"]
                assert sha(HERE / candidate["construction"]) == digest
                result = audit(attempt, saved, case, ident, digest, diagnostic=True,
                               decoded=decoded if first is None else None)
                assert result["camera_source_shape_passed"] and not result["passed"]
                assert not result["delivery_accepted"] and not result["owner_release_verified"]
                assert set(result["camera_sources"]) == set(CAMERAS)
                rejects(lambda: audit(attempt, saved, case, ident, digest),
                        "Synthetic source cannot establish original Native delivery")
                if first is None:
                    first = (attempt, saved, case, ident, digest)
                candidates += 1
                camera_checks += len(CAMERAS)
    assert len(cases) == 8 and candidates == 32 and camera_checks == 128
    assert len(decoded) >= 2
    attempt, saved, case, ident, digest = first
    with tempfile.TemporaryDirectory() as directory:
        temp = Path(directory)
        for name in (*SOURCES, "four-view-receipt.json", "raw.mkv", *(c + ".mkv" for c in CAMERAS)):
            dest = temp / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.symlink_to((attempt / name).resolve())
        (temp / "approach.mkv").unlink()
        rejects(lambda: audit(temp, saved, case, ident, digest, diagnostic=True),
                "Missing original camera source: approach")
        (temp / "approach.mkv").symlink_to((attempt / "approach.mkv").resolve())
        bad = json.loads(saved.read_text())
        bad["original_source_hashes"]["overview.mkv"] = "0" * 64
        bad_path = temp / "bad-processing.json"
        bad_path.write_text(json.dumps(bad))
        rejects(lambda: audit(temp, bad_path, case, ident, digest, diagnostic=True),
                "Saved camera source hash differs: overview")
    # Exercise the closure contract with in-memory shapes only. These are not
    # source receipts and never enter the positive delivery path.
    cameras = {name: {"sha256": str(index) * 64} for index, name in enumerate(CAMERAS, 1)}
    seal = {"provenance_kind": "native", "diagnostic_fixture": False,
            "sources": {name + ".mkv": row["sha256"] for name, row in cameras.items()}}
    exited = {"event": "native_exit", "native_process_exit_code": 0,
              "capture_seal_sha256": "a" * 64}
    release = {"event": "owner_release", "capture_seal_sha256": "a" * 64,
               "native_exit_sha256": "b" * 64, "case_id": case,
               "candidate_id": ident}
    started = {"events": ["saved_processing_started"],
               "owner_release_sha256": "c" * 64}
    check_release(seal, exited, release, started, case, ident, "a" * 64,
                  "b" * 64, "c" * 64, cameras)
    rejects(lambda: check_release(seal, exited, {**release, "native_exit_sha256": "0" * 64},
                                  started, case, ident, "a" * 64, "b" * 64,
                                  "c" * 64, cameras),
            "Native exit, owner release or camera seal differs")
    rejects(lambda: check_release(seal, exited, release, started, case, ident,
                                  "0" * 64, "b" * 64, "c" * 64, cameras),
            "Native exit, owner release or camera seal differs")
    rejects(lambda: check_release(seal, exited, release, {"events": []}, case, ident,
                                  "a" * 64, "b" * 64, "c" * 64, cameras),
            "Native exit, owner release or camera seal differs")
    rejects(lambda: check_release(seal, exited, release, started, case, ident,
                                  "a" * 64, "b" * 64, "0" * 64, cameras),
            "Native exit, owner release or camera seal differs")
    proof = {"format": "c110454-camera-lifecycle-cpu-proof-v1", "cases": 8,
             "candidates": candidates, "camera_hash_and_frame_checks": camera_checks,
             "unique_full_camera_decodes": len(decoded),
             "negative_checks": ["synthetic_as_original_all_32", "missing_camera",
                                 "stale_saved_camera_hash", "wrong_exit_binding",
                                 "wrong_capture_seal", "missing_saved_processing_start",
                                 "wrong_owner_release_receipt"],
             "release_receipt_binding_tested": True,
             "original_native_or_delivery_acceptance_claimed": False}
    path = HERE / "update017-camera-lifecycle-proof.json"
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({**proof, "proof_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))


if __name__ == "__main__":
    main()
