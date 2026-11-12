"""Exercise the independent delivery source boundary for all six draft cases."""
import hashlib
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from delivery_audit import audit

SOURCES = (
    ("update017-selected-pair-probe-manifest.json", ".runtime-work/c110919-update017-selected-pair-probe"),
    ("draft-absent-reference-execution-manifest.json", ".runtime-work/c110919-update025-absent-matrix"),
    ("draft-green-release-execution-manifest.json", ".runtime-work/c110919-update027-green-matrix"),
)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rejects(action, expected):
    try:
        action()
    except ValueError as error:
        if expected not in str(error):
            raise AssertionError("Wrong delivery rejection: " + str(error)) from error
        return str(error)
    raise AssertionError("Damaged delivery evidence was accepted")


def main():
    outputs = HERE / "update029-delivery-variant-audit"
    outputs.mkdir(exist_ok=True)
    records = []
    for manifest_name, run_root in SOURCES:
        manifest = json.loads((HERE / manifest_name).read_text())
        for entry in manifest["cases"]:
            suffix = entry["case_id"].removeprefix(HERE.name + "__")
            run = ROOT / run_root / suffix / "primary"
            attempt = run / "compatibility"
            processing = run / "saved/v0001/processing.json"
            receipt = audit(entry["case_id"], entry["construction_sha256"],
                            attempt, processing, diagnostic=True)
            if receipt["passed"] is not False or receipt["source_shape_passed"] is not True or \
               any(receipt["checks"].values()) or \
               receipt["physical_or_legal_acceptance_claimed"] is not False:
                raise AssertionError("Diagnostic delivery source promoted to acceptance")
            path = outputs / (suffix + ".json")
            path.write_text(json.dumps(receipt, indent=2) + "\n")
            negatives = {}
            negatives["wrong_construction"] = rejects(
                lambda: audit(entry["case_id"], "0" * 64, attempt, processing,
                              diagnostic=True),
                "Delivery construction differs from selected manifest")
            negatives["synthetic_as_original"] = rejects(
                lambda: audit(entry["case_id"], entry["construction_sha256"],
                              attempt, processing, diagnostic=False),
                "Original" if not suffix.startswith("green_release") else "Green-release")
            with tempfile.TemporaryDirectory(prefix="c110919-delivery-missing-",
                                             dir=ROOT / ".runtime-work") as folder:
                damaged = Path(folder)
                for name in ("native_samples.jsonl", "video_frames.jsonl", "capture/evidence.jsonl",
                             "body_history.jsonl", "trace.jsonl", "overview.mkv", "approach.mkv",
                             "reference_corner.mkv", "driver_reference.mkv", "result.json"):
                    target = damaged / name
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.symlink_to(attempt / name)
                negatives["missing_road_source"] = rejects(
                    lambda: audit(entry["case_id"], entry["construction_sha256"],
                                  damaged, processing, diagnostic=True),
                    "Missing delivery source: road_geometry.json")
            records.append({"case_id": entry["case_id"],
                            "construction_sha256": entry["construction_sha256"],
                            "manifest_sha256": sha(HERE / manifest_name),
                            "receipt": str(path.relative_to(HERE)),
                            "receipt_sha256": sha(path),
                            "negative_rejections": negatives,
                            "original_native_accepted": False})
    if len(records) != 6:
        raise ValueError("Six exact delivery draft cases were not checked")
    proof = {"format": "c110919-six-case-delivery-audit-cpu-proof-v1",
             "auditor_sha256": sha(HERE / "delivery_audit.py"),
             "cases": records, "positive_source_shapes": 6,
             "negative_rejections": 18,
             "canonical_selected": False, "original_native_accepted": False}
    path = HERE / "update029-delivery-variant-audit-proof.json"
    path.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"cases": 6, "negative_rejections": 18,
                      "proof_sha256": sha(path), "original_native_accepted": False}))


if __name__ == "__main__":
    main()
