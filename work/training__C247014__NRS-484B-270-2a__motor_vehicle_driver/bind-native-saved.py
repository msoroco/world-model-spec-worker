"""Retain source-bound recorded-only CPU receipts for four exact draft cases."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SUFFIXES = ("witness_1", "witness_2", "exception_1_1", "exception_1_2",
            "exception_unsafe_available")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scratch", type=Path, required=True)
    args = parser.parse_args()
    scratch = args.scratch.resolve()
    if REPO / ".runtime-work" not in scratch.parents:
        raise ValueError("Scratch must be under .runtime-work")
    manifest = json.loads((HERE / "selected-native-draft-manifest.json").read_text())
    entries = {item["case_id"].rsplit("__", 1)[-1]: item for item in manifest["cases"]}
    if set(entries) != set(SUFFIXES):
        raise ValueError("Exact draft case inventory differs")
    output = []
    for suffix in SUFFIXES:
        entry = entries[suffix]
        case_scratch = (REPO / ".runtime-work" / "c247014-resume-v6"
                        if suffix == "exception_unsafe_available" else scratch)
        versions = sorted((case_scratch / ("saved-" + suffix)).glob("v*/processing.json"))
        receipts = [(path, json.loads(path.read_text())) for path in versions]
        passed = [(path, item) for path, item in receipts if item.get("passed") is True]
        if len(passed) != 1:
            raise ValueError("Expected one passing recorded-only receipt: " + suffix)
        path, receipt = passed[0]
        if (receipt.get("case_id") != entry["case_id"] or
                receipt.get("candidate_id") != "primary" or
                receipt.get("recorded_only") is not True or
                receipt.get("originals_preserved") is not True or
                receipt.get("missing_evidence") is not False or
                receipt.get("physical_acceptance_claimed") is not False or
                receipt.get("legal_acceptance_claimed") is not False or
                receipt.get("analysis_revision", {}).get("construction_sha256") != entry["construction_sha256"] or
                receipt.get("analysis_revision", {}).get("runtime_manifest_sha256") != manifest["runtime_manifest_sha256"] or
                receipt.get("timestamp_joins", {}).get("frames") != 600 or
                receipt.get("timestamp_joins", {}).get("passed") is not True or
                receipt.get("final_video_checks", {}).get("passed") is not True or
                receipt.get("final_video_checks", {}).get("frames") != 600):
            raise ValueError("Recorded-only source or result check differs: " + suffix)
        dest = HERE / "selected-native-draft" / suffix / "saved-proof"
        dest.mkdir(exist_ok=True)
        target = dest / "processing.json"
        shutil.copyfile(path, target)
        log = dest / "saved.log"
        source_log = case_scratch / ("saved-" + suffix + ".log")
        shutil.copyfile(source_log, log)
        output.append({"case_id": entry["case_id"], "receipt": str(target.relative_to(HERE)),
                       "receipt_sha256": sha(target), "log": str(log.relative_to(HERE)),
                       "log_sha256": sha(log), "source_count": len(receipt["original_source_hashes"]),
                       "source_directory": str(path.parent)})
    negative_versions = sorted((scratch / "saved-witness_1-negative").glob("v*/processing.json"))
    if len(negative_versions) != 1:
        raise ValueError("Missing negative recorded-only result")
    negative_receipt = json.loads(negative_versions[0].read_text())
    feedback_path = negative_versions[0].parent / "feedback.json"
    feedback = json.loads(feedback_path.read_text())
    if (negative_receipt.get("missing_evidence") is not True or
            negative_receipt.get("originals_preserved") is not True or
            feedback.get("classification") != "incomplete_or_unavailable_law_evidence" or
            "Missing required source: pass-context.json" not in feedback.get("error", "")):
        raise ValueError("Saved missing-source feedback changed")
    negative_folder = HERE / "selected-native-draft" / "witness_1" / "saved-proof"
    negative_target = negative_folder / "negative-processing.json"
    feedback_target = negative_folder / "negative-feedback.json"
    shutil.copyfile(negative_versions[0], negative_target)
    shutil.copyfile(feedback_path, feedback_target)
    result = {"format": "c247014-recorded-only-draft-proof", "case_count": len(output),
              "runtime_manifest_sha256": manifest["runtime_manifest_sha256"],
              "cases": output,
              "negative": {"case_id": HERE.name + "__witness_1",
                           "removed": "pass-context.json",
                           "processing": str(negative_target.relative_to(HERE)),
                           "processing_sha256": sha(negative_target),
                           "feedback": str(feedback_target.relative_to(HERE)),
                           "feedback_sha256": sha(feedback_target)},
              "physical_or_legal_acceptance_claimed": False}
    target = HERE / "native" / "recorded-only-proof.json"
    target.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"case_count": len(output), "proof_sha256": sha(target)}, sort_keys=True))


if __name__ == "__main__":
    main()
