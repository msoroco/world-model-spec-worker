"""Retain three source-shaped physical outcomes and ownership-order proof."""

import hashlib
import json
from pathlib import Path
from one_way_variant import TARGETS
import subprocess
import sys


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def relative(path):
    return str(Path(path).relative_to(HERE))


def build(suffix):
    case = HERE.name + "__" + suffix
    source = HERE / "fixture-source" / suffix / "tunnel-rows.jsonl"
    context = HERE / "fixture-source" / suffix / "tunnel-context.json"
    rows = source.read_text().splitlines()
    output = HERE / "physical-proof" / suffix
    output.mkdir(parents=True, exist_ok=True)
    incomplete = output / "incomplete-tunnel-rows.jsonl"
    incomplete.write_text("\n".join(rows[:300]) + "\n")
    fixtures = []
    for kind, selected in (("complete_motion", source),
                           ("incomplete_motion", incomplete),
                           ("missing_evidence", output / "absent-tunnel-rows.jsonl")):
        target = output / (kind + ".json")
        log = output / (kind + ".log")
        command = [sys.executable, "-B", str(HERE / "physical_preparation.py"),
            "--source", str(selected), "--context", str(context),
            "--case", case, "--kind", kind, "--output", str(target)]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        log.write_text(result.stdout.rstrip() + "\n")
        fixtures.append({"kind": kind, "command": " ".join(command),
            "exit_code": result.returncode, "log": relative(log),
            "log_sha256": sha(log), "result": relative(target),
            "result_sha256": sha(target)})
    lifecycle = {"events": ["capture_finished", "encoders_closed",
        "restoration_verified", "native_exit", "owner_released",
        "saved_processing_started"], "exit_code": 0,
        "scope": "synthetic event-order proof; no Native ownership claimed"}
    log = output / "lifecycle.log"
    log.write_text("\n".join(lifecycle["events"]) + "\n")
    lifecycle.update(log=relative(log), log_sha256=sha(log))
    construction = HERE / ("one-way-construction-" + suffix + "-primary.json")
    receipt = {"format": "worker-physical-preparation",
        "case_id": case, "construction_sha256": sha(construction),
        "fixtures": fixtures, "lifecycle": lifecycle,
        "physical_acceptance_claimed": False}
    path = HERE / ("physical-preparation-" + suffix + ".json")
    path.write_text(json.dumps(receipt, indent=2, allow_nan=False) + "\n")
    return path


if __name__ == "__main__":
    for suffix in TARGETS:
        path = build(suffix)
        print(json.dumps({"receipt": path.name, "sha256": sha(path)}))
