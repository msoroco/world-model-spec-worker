"""Bind independent delivery checks to the selected 320-frame diagnostics."""

from copy import deepcopy
import json
from pathlib import Path
import shlex
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / "execution-manifest.json"


def bind():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest["cases"]:
        if "__yield_release_delay-" not in entry["case_id"]:
            continue
        short = entry["case_id"].rsplit("__", 1)[-1]
        matches = sorted((ROOT / ".runtime-work").glob(
            short + "-full-window-primary-compat-*"),
            key=lambda path: path.stat().st_mtime_ns)
        if not matches:
            raise ValueError("Missing selected full-window compatibility attempt: " + short)
        attempt = matches[-1]
        report = attempt / "analysis-report.json"
        if not report.is_file():
            raise ValueError("Missing full-window selected analysis: " + short)
        measured = json.loads(report.read_text())["measurements"]["intersection_observation"]["value"]
        expected = json.loads((HERE / entry["construction"]).read_text())
        config = json.loads(next(item["content"] for item in expected["files"]
                                 if item["path"] == "config.json"))
        if (config["release_delay_frames"] != measured["subject_entry_frame"] - 38038 or
                len((attempt / "video_frames.jsonl").read_text().splitlines()) != 320):
            raise ValueError("Selected full-window original entry differs from construction")
        altered = deepcopy(json.loads(report.read_text()))
        altered["measurements"]["intersection_observation"]["sources"][
            "intersection_participants.jsonl"] = "0" * 64
        tampered = ROOT / ".runtime-work" / (short + "-full-window-tampered-report.json")
        tampered.write_text(json.dumps(altered, indent=2) + "\n")
        script = HERE / entry["delivery_acceptance"]["script"]
        common = [sys.executable, str(script), "--case", entry["case_id"],
                  "--attempt", str(attempt), "--report"]
        entry["delivery_acceptance"]["command"] = shlex.join(common + [str(report)])
        entry["delivery_acceptance"]["negative_command"] = shlex.join(common + [str(tampered)])
        print(short, "frames=320 entry=", measured["subject_entry_frame"], flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    bind()
