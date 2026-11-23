"""Exercise each exact comparison CLI on clean, labeled synthetic attempts."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT))
from prove_delivery_diagnostics import KINDS, prepare, prepare_synthetic_response_pair
from delivery_audit import REVIEW_SOURCES, audit_media_time
from independent.comparison_audit import SPECS


def run_command(comparison_id: str, left: Path, right: Path, output: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(ROOT / "independent/comparison_audit.py"),
         "--comparison-id", comparison_id, "--left-attempt", str(left),
         "--right-attempt", str(right), "--output", str(output), "--diagnostic"],
        capture_output=True, text=True, check=False)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--compat-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    base = (REPO / ".runtime-work").resolve()
    runtime_output = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    compat = args.compat_root.resolve()
    output = args.output_root.resolve()
    if not all(path.is_relative_to(base) for path in (compat, output, runtime_output)):
        raise ValueError("diagnostic paths must stay under .runtime-work")
    output.mkdir(parents=True, exist_ok=False)
    for kind in KINDS:
        frames = prepare(compat / kind, output / kind, ROOT.name + "__" + kind)
        audit_media_time(output / kind, frames)
    prepare_synthetic_response_pair(output)
    for comparison_id, (left, right, differences) in SPECS.items():
        receipt = output / (comparison_id + ".json")
        result = run_command(comparison_id, output / left, output / right, receipt)
        if result.returncode != 0:
            raise AssertionError(comparison_id + " failed: " + result.stderr)
        body = json.loads(receipt.read_text())
        if (body["comparison_id"] != comparison_id or
                body["declared_differences"] != sorted(differences) or
                not body["diagnostic_fixture"] or body["physical_acceptance_claimed"] or
                body["legal_verdict_claimed"]):
            raise AssertionError(comparison_id + " receipt misstates evidence")
        same = run_command(comparison_id, output / left, output / left,
                           output / (comparison_id + "-invalid.json"))
        if same.returncode == 0 or "reuses one original attempt" not in same.stderr:
            raise AssertionError(comparison_id + " accepted one reused attempt")
        print(comparison_id + ": exact CLI positive and reused-attempt negative passed", flush=True)
    changed = output / "wide_same_crossing" / REVIEW_SOURCES["device_inventory_source"]
    changed.write_bytes(changed.read_bytes() + b"changed\n")
    stale = run_command("separate_roadway_intersection", output / "precedence",
                        output / "wide_same_crossing", output / "stale-invalid.json")
    if stale.returncode == 0 or "original source missing or changed" not in stale.stderr:
        raise AssertionError("exact CLI accepted a changed source")
    print("separate_roadway_intersection: changed-source negative passed", flush=True)


if __name__ == "__main__":
    main()
