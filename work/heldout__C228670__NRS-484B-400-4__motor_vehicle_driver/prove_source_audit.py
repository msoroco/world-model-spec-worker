"""Run the independent saved-source audit on the three primary diagnostics."""
import json
from pathlib import Path
import shutil
import tempfile

from turn_source_audit import SOURCES, audit

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SLUGS = ("approach_near_depart_right", "approach_far_depart_right",
         "approach_near_depart_left")


def main():
    proofs = []
    for slug in SLUGS:
        for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
            original = REPO / ".runtime-work" / ("c228670-saved-" + slug + "-" + candidate + "-attempt-v1")
            saved = REPO / ".runtime-work" / ("c228670-saved-" + slug + "-" + candidate + "-v1/v0001/analysis")
            proof = audit(saved, original)
            proof["candidate_id"] = candidate
            proofs.append(proof)
            print(slug, candidate, "original sources, measurements and four full camera decodes passed", flush=True)
    original = REPO / ".runtime-work/c228670-saved-approach_near_depart_right-primary-attempt-v1"
    saved = REPO / ".runtime-work/c228670-saved-approach_near_depart_right-primary-v1/v0001/analysis"
    with tempfile.TemporaryDirectory(dir=REPO / ".runtime-work") as directory:
        altered = Path(directory)
        for name in ("config.json",) + SOURCES:
            shutil.copy2(original / name, altered / name)
        target = altered / "body_footprints.jsonl"
        target.write_text(target.read_text() + "\n")
        try:
            audit(saved, altered, decode=False)
        except ValueError as exc:
            if "Saved original source changed" not in str(exc):
                raise
        else:
            raise AssertionError("Altered original body source was accepted")
    (HERE / "source-audit-proof.json").write_text(json.dumps({
        "format": "worker-turn-saved-source-audit-proof", "cases": proofs,
        "altered_original_rejected": True,
        "physical_acceptance_claimed": False, "legal_acceptance_claimed": False}, indent=2) + "\n")
    print("Altered original rejected", flush=True)


if __name__ == "__main__":
    main()
