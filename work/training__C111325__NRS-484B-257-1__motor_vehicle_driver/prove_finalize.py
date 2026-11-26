"""Exercise selected saved-only finalizer with disposable diagnostic sources."""

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from finalize import finalize
from prove_statutory_measurement import packet
from worker_exchange.measurement_contract import validate as validate_contract, verify_report


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rejects(root, output, phrase):
    try:
        finalize(root, output)
    except ValueError as error:
        if phrase not in str(error):
            raise AssertionError(str(error)) from error
        return
    raise AssertionError("Invalid selected saved packet passed")


def main():
    source = Path(__file__).resolve().parent
    scratch = source.parents[1] / ".runtime-work" / "nrs257-finalizer-tests"
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="selected-", dir=scratch) as temporary:
        root = Path(temporary)
        context, motion = packet("complete_stop_then_yield")
        mapping = {"map": "road.xodr", "sign": "governing_sign.json",
                   "reference": "stopping_reference.json", "controls": "governing_controls.json",
                   "through_road": "through_road.json", "ego_body": "ego_body.jsonl",
                   "through_body": "through_body.jsonl"}
        for name, relative in mapping.items():
            path = root / relative
            path.write_text(json.dumps({"synthetic_diagnostic": True, "name": name}) + "\n")
            context[name + "_sha256"] = sha(path)
        context["source_files"] = mapping
        (root / "stop_yield_context.json").write_text(json.dumps(context, indent=2) + "\n")
        (root / "stop_yield_motion.jsonl").write_text("".join(json.dumps(row) + "\n" for row in motion))
        (root / "config.json").write_bytes((source / "config.json").read_bytes())
        (root / "trace.jsonl").write_text("".join(json.dumps({"frame": row["native_frame"],
            "time_s": row["time_s"], "position": {"x": row["ego_x_m"], "y": -1.75, "z": .5},
            "heading_deg": 0, "speed_mps": row["ego_speed_mps"]}) + "\n" for row in motion))
        (root / "video_frames.jsonl").write_text("".join(json.dumps({"video_frame": row["video_frame"],
            "native_frame": row["native_frame"], "carla_frame": row["native_frame"],
            "time_s": row["time_s"], "source_cameras": row["source_cameras"]}) + "\n"
            for row in motion))
        for name in ("overview", "approach", "reference_corner", "driver_reference"):
            subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i",
                            "color=c=black:s=16x16:r=20:d=30", "-frames:v", "600",
                            "-c:v", "ffv1", str(root / (name + ".mkv"))], check=True,
                           stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, timeout=120)
        report = finalize(root, root / "analysis-report.json")
        result = json.loads((root / "result.json").read_text())
        contract = json.loads((source / "measurement-complete_stop_then_yield.json").read_text())
        plan = json.loads((source / "case-plan.json").read_text())
        validate_contract(contract, plan["requirement_dispositions"],
                          (source / "finalize.py").read_text(), contract["case_id"])
        verify_report(contract, report, root)
        assert len(report["measurements"]) == 4
        assert result["diagnostic_fixture"] is True and result["setup_confirmed"] is False
        assert "legal_verdict" not in result["measured_values"]
        (root / "governing_sign.json").unlink()
        rejects(root, root / "invalid-report.json", "Missing required source: governing_sign.json")
        print("selected finalizer: four source-bound contract measurements and missing-sign rejection passed")


if __name__ == "__main__":
    main()
