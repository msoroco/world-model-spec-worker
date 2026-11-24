"""Materialize the assignment root construction and current CPU tests."""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
NATIVE = HERE / "native"


def build():
    config = json.loads((NATIVE / "config.json").read_text())
    config["supported_case_ids"] = [HERE.name + "__" + suffix for suffix in (
        "probe_a", "probe_b", "pursuit", "call_lamps_only", "ordinary_lamps_only")]
    names = ("runner.py", "geometry.py", "motion.py", "capture_native.py",
             "finalize.py", "source_acquisition.py", "measure.py", "audit.py",
             "audit_original.py", "prove.py")
    files = [{"path": "config.json", "content": json.dumps(config, indent=2) + "\n"}]
    (HERE / "config.json").write_text(files[0]["content"])
    for name in names:
        content = (NATIVE / name).read_text()
        (HERE / name).write_text(content)
        files.append({"path": name, "content": content})
    draft = json.loads((HERE / "draft-candidates/probe_a/primary/construction.json").read_text())
    test = next(item["content"] for item in draft["files"]
                if item["path"] == "tests/test_source.py")
    (HERE / "tests").mkdir(exist_ok=True)
    (HERE / "tests/test_source.py").write_text(test)
    files.append({"path": "tests/test_source.py", "content": test})
    construction = {"case_id": config["case_id"], "law_id": config["law_id"],
        "cell_id": config["cell_id"], "actor": config["actor"],
        "entrypoint": "runner.py", "files": files,
        "recording_description": config["recording_description"],
        "measurement_plan": {"sources": [
            "native_samples.jsonl", "video_frames.jsonl", "trace.jsonl",
            "capture/evidence.jsonl", "microphone-pcm16.json",
            "audio_observations.jsonl", "dispatch.jsonl",
            "dispatch-source.json", "vehicle-authorization.json",
            "acoustic-report.json"],
            "analysis": "saved-only source and frame join in finalize.py"},
        "mechanisms": ["authored OpenDRIVE crossroads", "original Native actor and camera readback",
                       "independent microphone PCM and dispatch source join"],
        "static_checks": ["600 frames at 20 Hz", "four source cameras",
                          "original audio and dispatch hash checks"],
        "termination_rules": {"frames": 600,
                              "failure": "incomplete original acquisition or restoration"}}
    (HERE / "construction.json").write_text(json.dumps(construction, indent=2) + "\n")
    return construction


if __name__ == "__main__":
    print(json.dumps({"root_files": len(build()["files"])}))
