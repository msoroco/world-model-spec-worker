"""Saved-only railway analysis and video finalization after Native owner release."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from analysis import analyze
from rail_media_finalize import finalize
from rail_saved_measurement import _source


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _owner_released(attempt, owner_release_receipt):
    """Admit only the operator release for this construction and Native exit."""
    release_path = Path(owner_release_receipt)
    if not release_path.is_file() or release_path.is_symlink():
        raise ValueError("rail owner-release receipt missing")
    release = json.loads(release_path.read_text())
    construction = attempt / "construction.json"
    native_exit = attempt / "native-exit.json"
    if (not construction.is_file() or construction.is_symlink() or
            not native_exit.is_file() or native_exit.is_symlink() or
            release.get("event") != "owner_released" or
            release.get("operator_attested") is not True or
            release.get("native_construction_sha256") != _sha(construction) or
            release.get("native_exit_sha256") != _sha(native_exit)):
        raise ValueError("rail owner release differs from original Native exit")
    return _sha(release_path)


def process(attempt, contract, case_id, owner_release_receipt):
    """Require complete saved sources before creating any media or report."""
    attempt = Path(attempt).resolve()
    contract = Path(contract).resolve()
    if any((attempt / name).exists() or (attempt / name).is_symlink() for name in
           ("rail-analysis.json", "rail-media-receipt.json", "saved-rail-result.json")):
        raise ValueError("rail postprocessing output already exists")
    release_hash = _owner_released(attempt, owner_release_receipt)
    analysis = analyze(attempt, contract, case_id)
    receipt_path = attempt / "native-rail-receipt.json"
    receipt = json.loads(receipt_path.read_text())
    packet = json.loads(_source(attempt, receipt.get("packet")).read_text())
    media = finalize(attempt, packet, case_id)
    if set(media["media"]) != set(analysis["camera_views"]):
        raise ValueError("rail saved media and original views differ")
    analysis_path = attempt / "rail-analysis.json"
    analysis_path.write_text(json.dumps(analysis, indent=2, sort_keys=True) + "\n")
    media_path = attempt / "rail-media-receipt.json"
    result = {
        "case_id": case_id, "capture_kind": "saved_original_native",
        "source_receipt_sha256": _sha(receipt_path),
        "owner_release_sha256": release_hash,
        "analysis_path": analysis_path.name, "analysis_sha256": _sha(analysis_path),
        "media_receipt_path": media_path.name,
        "media_receipt_sha256": _sha(media_path),
        "original_frame_count": 900, "camera_views": analysis["camera_views"],
        "physical_completion_confirmed": False, "legal_conclusion": None,
    }
    (attempt / "saved-rail-result.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--owner-release-receipt", type=Path, required=True)
    args = parser.parse_args()
    result = process(args.attempt, args.contract, args.case_id,
                     args.owner_release_receipt)
    print(json.dumps({"case_id": result["case_id"],
                      "saved_source_complete": True,
                      "physical_completion_confirmed": False}))


if __name__ == "__main__":
    main()
