"""Reject right/left sign substitutions for the frozen intended U-turn."""
from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from native.delivery_audit import check_sources, sha

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASES = (("controlled_2", "bicycle"),
         ("electric_bicycle_turn", "electric_bicycle"),
         ("electric_scooter_turn", "electric_scooter"))


def main() -> None:
    results = []
    for label, machine in CASES:
        case_id = ROOT.name + "__" + label
        base = ROOT / "v2-mounted-turn-primary-source"
        rider = (base / "rider_native_samples.jsonl" if machine == "bicycle" else
                 ROOT / "electric-drafts" / label / "rider_native_samples.jsonl")
        with tempfile.TemporaryDirectory(dir=REPO / ".runtime-work", prefix="c104538-sign-negative-") as name:
            stage = Path(name)
            for source in ("trace.jsonl", "video_frames.jsonl", "native_samples.jsonl"):
                shutil.copyfile(base / source, stage / source)
            shutil.copyfile(rider, stage / "rider_native_samples.jsonl")
            marks = ({"frame": frame, "sign_visible": True,
                      "rider_visible": True, "machine_visible": True} for frame in range(600))
            (stage / "pixel_review.jsonl").write_text(
                "".join(json.dumps(row) + "\n" for row in marks))
            packet = {"source_kind": "synthetic_diagnostic", "governs_approach": True,
                      "native_samples_sha256": sha(stage / "native_samples.jsonl"),
                      "frame_map_sha256": sha(stage / "video_frames.jsonl"),
                      "rider_samples_sha256": sha(stage / "rider_native_samples.jsonl"),
                      "pixel_review_sha256": sha(stage / "pixel_review.jsonl")}
            outcomes = {}
            for code in ("no_u_turn", "no_left_turn", "no_right_turn"):
                (stage / "sign-review.json").write_text(json.dumps({**packet, "sign_code": code}) + "\n")
                try:
                    check_sources(stage, case_id, diagnostic=True)
                except ValueError as error:
                    outcomes[code] = {"accepted": False, "error": str(error)}
                else:
                    outcomes[code] = {"accepted": True}
            if (outcomes["no_u_turn"]["accepted"] is not True or
                    any(outcomes[code] != {"accepted": False,
                                           "error": "Applicable prohibition device unverified"}
                        for code in ("no_left_turn", "no_right_turn"))):
                raise ValueError("U-turn sign negative control failed: " + label)
            results.append({"case_id": case_id, "machine_class": machine,
                            "source_hashes": {"native": sha(base / "native_samples.jsonl"),
                                              "rider": sha(rider)},
                            "outcomes": outcomes})
    report = {"format": "c104538-within-scope-sign-negative-controls-v1",
              "scope": "synthetic exact U-turn source rows and independent delivery auditor",
              "statutory_right_left_coverage_claimed": False,
              "physical_or_legal_acceptance_claimed": False,
              "auditor_sha256": sha(ROOT / "native/delivery_audit.py"),
              "cases": results}
    output = ROOT / "within-scope-sign-controls.json"
    output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"cases": len(results), "report_sha256": hashlib.sha256(output.read_bytes()).hexdigest()},
                     sort_keys=True))


if __name__ == "__main__":
    main()
