"""Pinned exact v1 package probe and removed-source negative for C111294."""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "runtime/pipeline/scenario_pipeline"))
spec = importlib.util.spec_from_file_location("c111294_fixture", HERE / "probe-saved-integration.py")
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
spec2 = importlib.util.spec_from_file_location("c111294_graphs", HERE / "probe-core-synthetic.py")
graphs = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(graphs)
from worker_exchange.package_compatibility import run, materialize_case
from worker_exchange.runtime_cli import execution_env


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suffix", choices=("probe_a", "probe_b"),
                        default="probe_a")
    parser.add_argument("--candidate", choices=("primary", "fallback1", "fallback2", "fallback3"),
                        default="primary")
    args = parser.parse_args()
    scratch = Path(tempfile.mkdtemp(dir=ROOT / ".runtime-work",
                                        prefix="c111294-exact-package-"))
    source = scratch / "fixture"
    fixture.make_attempt(source, args.suffix, full_resolution=True)
    graphs.add_graphs(source)
    (source / "config.json").unlink()
    (source / "measurement-contract.json").unlink()
    case = "training__C111294__NRS-484B-603-1__motor_vehicle_driver__" + args.suffix
    manifest = HERE / "draft-execution-manifest.json"
    output = scratch / "output"
    receipt = run(manifest, case, source, output,
                  ROOT / "runtime/pipeline/library",
                  ROOT / ".runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck",
                  args.candidate)
    negative = scratch / "negative"
    materialize_case(manifest, case, negative, source, args.candidate)
    (negative / "native_samples.jsonl").unlink()
    failure = subprocess.run([sys.executable, str(negative / "finalize.py"),
        "--attempt", str(negative), "--output", str(negative / "analysis-report.json")],
        cwd=negative, env=execution_env(), text=True, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, timeout=300)
    (scratch / "negative-analysis.log").write_text(failure.stdout)
    expected = "Missing required source: native_samples.jsonl"
    if failure.returncode == 0 or expected not in failure.stdout:
        raise ValueError("Exact missing-source negative did not reject: " + failure.stdout[-2000:])
    result = {"case_id": case, "candidate_id": args.candidate,
              "positive": {k: v for k, v in receipt.items() if k != "fixture_manifest"},
              "negative": {"exit_code": failure.returncode,
                           "source_removed": "native_samples.jsonl",
                           "error_contains": expected,
                           "log_sha256": fixture.sha(scratch / "negative-analysis.log")},
              "scratch": str(scratch), "ready": False,
              "scope": "unselected exact synthetic v1 software compatibility only"}
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__": main()
