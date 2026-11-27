"""Saved-only synthetic finalizer check, including four decoded source videos."""

import json
import subprocess
import tempfile
from pathlib import Path

from finalize import CAMERAS, finalize
from test_saved_due_care import CASE, ROOT, fixture, write_rows


def main():
    scratch = ROOT / ".runtime-work"
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=scratch, prefix="c230266-finalize-") as temporary:
        attempt = Path(temporary)
        construction = json.loads((ROOT / "work" / CASE.split("__selected_")[0] /
                                   "native/selected-a-construction.json").read_text())
        config = next(item["content"] for item in construction["files"]
                      if item["path"] == "config.json")
        (attempt / "config.json").write_text(config)
        source, mapping = fixture(attempt)
        write_rows(attempt / "trace.jsonl", [{"frame": row["native_frame"],
                                              "time_s": row["time_s"],
                                              "position_m": [row["ego_x_m"], row["ego_y_m"], 0.5],
                                              "speed_mps": row["ego_speed_mps"]} for row in source])
        capture = attempt / "capture"
        capture.mkdir()
        write_rows(capture / "evidence.jsonl", [{"original_frame": row["native_frame"],
                                                  "recording_time_s": row["time_s"],
                                                  "synthetic_diagnostic": True} for row in source])
        for name in CAMERAS:
            subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                            "-f", "lavfi", "-i", "color=c=blue:s=64x64:r=20",
                            "-frames:v", "600", "-an", "-c:v", "ffv1", "-threads", "1",
                            str(attempt / (name + ".mkv"))], check=True, timeout=120)
        contact = attempt / "contact_events.jsonl"
        saved = contact.read_text()
        contact.unlink()
        try:
            finalize(attempt, attempt / "analysis-report.json")
        except ValueError as error:
            assert "Missing required source: contact_events.jsonl" in str(error), str(error)
            rejection = str(error)
        else:
            raise AssertionError("Missing contact source accepted")
        contact.write_text(saved)
        report = finalize(attempt, attempt / "analysis-report.json")
        result = json.loads((attempt / "result.json").read_text())
        assert report["four_camera_frames"] == {name + ".mkv": 600 for name in CAMERAS}
        assert report["measurements"]["pedestrian_encounter_gap"]["value"] >= 0
        assert result["case_id"] == CASE and result["physical_checks"]["due_care_diagnostics"]["contact_frames"] == 1
        assert result["provenance_kind"] == "synthetic_cpu_fixture"
        assert not result["accepted"] and not report["legal_verdict_claimed"]
    proof = {"format": "worker-c230266-finalize-proof-v1", "case_id": CASE,
             "positive": {"frames": 600, "four_camera_frames": report["four_camera_frames"],
                          "contact_frames": 1, "synthetic_cpu_fixture": True},
             "negative_rejection": rejection, "actual_native_observed": False,
             "legal_verdict": None}
    Path(__file__).with_name("finalize-proof.json").write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"four_camera_frames": 600, "positive": True,
                      "negative": rejection, "physical": False}))


if __name__ == "__main__":
    main()
