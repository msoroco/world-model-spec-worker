"""All twelve unselected exact v1 positives and removed-source negatives."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "runtime/pipeline/scenario_pipeline"))


def module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


fixture = module("c111294_saved_fixture", HERE / "probe-saved-integration.py")
graphs = module("c111294_core_graphs", HERE / "probe-core-synthetic.py")
from worker_exchange.package_compatibility import run, materialize_case
from worker_exchange.runtime_cli import execution_env


def main() -> None:
    scratch = Path(tempfile.mkdtemp(dir=ROOT / ".runtime-work",
                                        prefix="c111294-all-packages-"))
    manifest = HERE / "draft-execution-manifest.json"
    records = []
    for suffix in ("below_80_mph", "inside_80_mph", "above_80_mph"):
        base = scratch / suffix
        base.mkdir()
        source = base / "fixture"
        fixture.make_attempt(source, suffix, full_resolution=True)
        graphs.add_graphs(source)
        (source / "config.json").unlink()
        (source / "measurement-contract.json").unlink()
        case = "training__C111294__NRS-484B-600-1e__motor_vehicle_driver__" + suffix
        for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
            output = base / (candidate + "-positive")
            receipt = run(manifest, case, source, output,
                ROOT / "runtime/pipeline/library",
                ROOT / ".runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck",
                candidate)
            negative = base / (candidate + "-negative")
            materialize_case(manifest, case, negative, source, candidate)
            (negative / "native_samples.jsonl").unlink()
            failure = subprocess.run([sys.executable, str(negative / "finalize.py"),
                "--attempt", str(negative), "--output", str(negative / "analysis-report.json")],
                cwd=negative, env=execution_env(), text=True, stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT, timeout=300)
            expected = "Missing required source: native_samples.jsonl"
            if failure.returncode == 0 or expected not in failure.stdout:
                raise ValueError("Exact missing-source negative did not reject: " + failure.stdout[-2000:])
            folder = HERE / "exact-drafts" / suffix / candidate
            shutil.copyfile(output / "compatibility-analysis.log", folder / "package-positive.log")
            (folder / "package-negative.log").write_text(failure.stdout)
            (folder / "package-receipt.json").write_text(
                json.dumps(receipt, indent=2, sort_keys=True) + "\n")
            records.append({"case_id": case, "candidate_id": candidate,
                "construction_sha256": receipt["construction_sha256"],
                "fixture_sha256": receipt["fixture_sha256"],
                "receipt_sha256": fixture.sha(folder / "package-receipt.json"),
                "positive_log_sha256": fixture.sha(folder / "package-positive.log"),
                "negative_log_sha256": fixture.sha(folder / "package-negative.log"),
                "negative_exit_code": failure.returncode,
                "positive_output": str(output),
                "negative_output": str(negative),
                "ready": False})
            print(suffix, candidate, "positive and negative passed", flush=True)
    summary = {"format": "c111294-unselected-exact-package-v1",
               "manifest_sha256": fixture.sha(manifest), "results": records,
               "all_passed": len(records) == 12,
               "scope": "synthetic software compatibility only; strict selected v2 unproved",
               "carla_executed": False, "accepted": False, "ready": False}
    (HERE / "exact-package-summary.json").write_text(json.dumps(summary, indent=2) + "\n")


if __name__ == "__main__": main()
