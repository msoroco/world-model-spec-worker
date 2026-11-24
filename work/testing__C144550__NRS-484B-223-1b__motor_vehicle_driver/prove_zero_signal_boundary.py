"""Construct and verify a synthetic zero-frame signal onset at lane departure.

This is a CPU source probe, not an accepted Native recording or exact delivery case.
The baseline is the source-hashed late-signal recipe. Only the ego lamp at the
first measured body departure is changed; all bodies and times stay fixed.
"""

import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from lane_change_measurements import analyze

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = HERE / "diagnostic-sources"
RECIPE = HERE / "cases/left_signal_late_clear_gap/diagnostic-recipe.json"
MAPPING = {
    "lane_history.jsonl": ("late-lane_history.jsonl", "zero-lane_history.jsonl"),
    "trace.jsonl": ("late-trace.jsonl", "zero-trace.jsonl"),
    "capture/evidence.jsonl": ("late-capture-evidence.jsonl", "zero-capture-evidence.jsonl"),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    recipe = json.loads(RECIPE.read_text())
    sources = {entry["path"]: entry for entry in recipe["sources"]}
    for relative, (name, _) in MAPPING.items():
        if digest(SOURCE / name) != sources[relative]["sha256"]:
            raise ValueError("Baseline recipe source changed: " + name)
    with tempfile.TemporaryDirectory(dir=ROOT / ".runtime-work", prefix="c144550-zero-") as temporary:
        attempt = Path(temporary)
        for relative in ("lane_context.json", "lane_history.jsonl", "video_frames.jsonl"):
            source = ROOT / sources[relative]["source"]
            if digest(source) != sources[relative]["sha256"]:
                raise ValueError("Baseline recipe source changed: " + relative)
            shutil.copyfile(source, attempt / relative)
        late = analyze(attempt)
        departure = late["first_body_leaves_lane"]["frame"]
        if departure != 101 or late["first_appropriate_signal"]["frame"] != departure + 1:
            raise ValueError("Expected late-source landmark moved")

        changed = {}
        for relative, (baseline, target) in MAPPING.items():
            rows = [json.loads(line) for line in (SOURCE / baseline).read_text().splitlines()]
            if len(rows) != 900:
                raise ValueError("Incomplete baseline source: " + baseline)
            matches = [row for row in rows if row.get("original_frame", row.get("frame")) == departure]
            if len(matches) != 1:
                raise ValueError("Departure frame missing or duplicated: " + baseline)
            row = matches[0]
            if relative == "lane_history.jsonl":
                if row["indicator"] != "off":
                    raise ValueError("Baseline departure lamp unexpectedly active")
                row["indicator"] = "left"
            elif relative == "trace.jsonl":
                if row["ego_lamp_bits"] != 0:
                    raise ValueError("Baseline departure lamp bits unexpectedly active")
                row["ego_lamp_bits"] = 32
            else:
                lamp = row["original_observations"]["participants"][0]["light_attributes"]
                if lamp["light_LeftBlinker"] or lamp["light_RightBlinker"]:
                    raise ValueError("Baseline departure capture lamp unexpectedly active")
                lamp["light_LeftBlinker"] = True
            output = SOURCE / target
            output.write_text("".join(json.dumps(item, separators=(",", ":")) + "\n" for item in rows))
            if output.stat().st_size > 2 * 1024 * 1024:
                raise ValueError("Returned zero source exceeds size limit: " + target)
            changed[relative] = {"baseline_sha256": digest(SOURCE / baseline),
                                 "zero_sha256": digest(output), "changed_original_frame": departure,
                                 "returned_source": str(output.relative_to(ROOT))}

        shutil.copyfile(SOURCE / MAPPING["lane_history.jsonl"][1], attempt / "lane_history.jsonl")
        zero = analyze(attempt)
        onset = zero["first_appropriate_signal"]["frame"]
        if onset != departure or zero["appropriate_signal_observed_before_movement"]:
            raise ValueError("Zero-frame signal ordering not measured")
        if len(zero["samples"]) != 900:
            raise ValueError("Incomplete zero-frame original history")
        if zero["samples"][1]["nearest_target_body_longitudinal_gap_m"] != 8.0:
            raise ValueError("Fixed target gap changed")
        report = {
            "format": "worker-c144550-zero-frame-synthetic-source-probe",
            "baseline_recipe_sha256": digest(RECIPE),
            "first_body_departure_frame": departure,
            "first_appropriate_signal_frame": onset,
            "signal_lead_frames": departure - onset,
            "source_frame_count": 900,
            "changed_sources": changed,
            "physical_acceptance_claimed": False,
            "legal_acceptance_claimed": False,
            "next_step": "Bind exact zero-frame case and run full offline, compatibility, saved and comparison proofs",
        }
        (HERE / "zero-signal-boundary-proof.json").write_text(json.dumps(report, indent=2) + "\n")
        return report


if __name__ == "__main__":
    report = build()
    print(json.dumps({"frame": report["first_body_departure_frame"],
                      "signal_lead_frames": report["signal_lead_frames"],
                      "source_frame_count": report["source_frame_count"]}, sort_keys=True))
