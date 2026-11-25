"""Prove three synthetic physical outcomes and ordered saved lifecycle per case."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ROOT = REPO / ".runtime-work/c202480-owner/physical"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path: Path, value) -> None:
    path.write_text(json.dumps(value, separators=(",", ":"), allow_nan=False) + "\n")


def call(script: str, fixture: Path, output: Path, log: Path, env: dict) -> None:
    command = [str(REPO / ".venv-cpu/bin/python"), str(HERE / script),
               "--fixture", str(fixture), "--output", str(output)]
    done = subprocess.run(command, cwd=REPO, env=env, text=True,
                          capture_output=True, timeout=120)
    log.write_text((done.stdout + done.stderr).rstrip("\n") + "\n")
    if done.returncode:
        raise ValueError(script + " failed: " + done.stderr[-1000:])


def main() -> None:
    ROOT.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ, SCENARIO_PIPELINE_OUTPUT_ROOT=str(ROOT),
               TMPDIR=str(ROOT), PYTHONDONTWRITEBYTECODE="1")
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        suffix = entry["case_id"].removeprefix(HERE.name + "__")
        base = ROOT / suffix
        if base.exists():
            shutil.rmtree(base)
        base.mkdir()
        construction = json.loads((HERE / entry["construction"]).read_text())
        config = json.loads(next(item["content"] for item in construction["files"]
                                 if item["path"] == "config.json"))
        outcomes = []
        for kind, expected in (("complete_motion", "met"),
                               ("incomplete_motion", "not_met"),
                               ("missing_evidence", "unverified")):
            fixture = base / kind
            fixture.mkdir()
            save(fixture / "config.json", config)
            mapping = [{"video_frame": i, "carla_frame": 1000 + i,
                        "time_s": i / 20} for i in range(900)]
            (fixture / "video_frames.jsonl").write_text(
                "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in mapping))
            if kind != "missing_evidence":
                distance = 130 if kind == "complete_motion" else 1
                trace = [{"frame": 1000 + i, "time_s": i / 20,
                          "position_m": [0, 130 - distance * i / 899, 0],
                          "speed_mps": distance / 45} for i in range(900)]
                (fixture / "trace.jsonl").write_text(
                    "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in trace))
            result = HERE / ("physical-" + suffix + "-" + kind + ".json")
            log = HERE / ("physical-" + suffix + "-" + kind + ".log")
            call("physical_probe.py", fixture, result, log, env)
            actual = json.loads(result.read_text())["physical_checks"]["maneuver"]["status"]
            if actual != expected:
                raise ValueError(suffix + " physical " + kind + " returned " + actual)
            outcomes.append({"kind": kind, "command": "physical_probe.py --fixture " +
                             str(fixture.relative_to(REPO)) + " --output " + result.name,
                             "exit_code": 0, "log": log.name, "log_sha256": sha(log),
                             "result": result.name, "result_sha256": sha(result)})
        lifecycle_fixture = base / "lifecycle"
        lifecycle_fixture.mkdir()
        save(lifecycle_fixture / "config.json", config)
        (lifecycle_fixture / "construction.json").write_bytes((HERE / entry["construction"]).read_bytes())
        (lifecycle_fixture / "runner.py").write_text(next(item["content"] for item in construction["files"]
                                                        if item["path"] == "runner.py"))
        (lifecycle_fixture / "trace.jsonl").write_text("{\"frame\":1000}\n")
        (lifecycle_fixture / "video_frames.jsonl").write_text("{\"carla_frame\":1000}\n")
        save(lifecycle_fixture / "acquisition-provenance.json",
             {"provenance_kind": "native", "diagnostic_fixture": False})
        life_result = base / "lifecycle-result.json"
        life_log = HERE / ("lifecycle-" + suffix + ".log")
        call("lifecycle_probe.py", lifecycle_fixture, life_result, life_log, env)
        life = json.loads(life_result.read_text())
        life.update(log=life_log.name, log_sha256=sha(life_log))
        receipt = HERE / ("physical-preparation-" + suffix + ".json")
        save(receipt, {"format": "worker-physical-preparation",
                       "case_id": entry["case_id"],
                       "construction_sha256": entry["construction_sha256"],
                       "fixtures": outcomes, "lifecycle": life,
                       "scope": "synthetic CPU event and closure proof only"})
        entry["physical_preparation"] = {"receipt": receipt.name, "sha256": sha(receipt)}
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
        print(suffix, "three physical outcomes and lifecycle passed", flush=True)


if __name__ == "__main__":
    main()
