"""Exact eight-bundle offline and saved positive/negative CPU diagnostic."""
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "runtime/pipeline/scenario_pipeline"))
from worker_exchange.runtime_cli import materialize, execution_env


def run_command(*args, cwd):
    result = subprocess.run([sys.executable, *map(str, args)], cwd=cwd,
                            env=execution_env(), text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
    return result


def main():
    manifest = HERE / "draft-execution-manifest.json"
    results = []
    with tempfile.TemporaryDirectory(dir=REPO / ".runtime-work", prefix="c110454-450-1c-") as scratch:
        root = Path(scratch)
        for suffix in ("probe_a", "probe_b"):
            case = HERE.name + "__" + suffix
            for candidate in ("primary", "fallback1", "fallback2", "fallback3"):
                output = root / (suffix + "-" + candidate)
                materialize(manifest, case, output, candidate)
                offline = run_command(output / "runner.py", "--check", cwd=output)
                if offline.returncode != 0:
                    raise RuntimeError("Offline runner failed: " + offline.stdout)
                receipt = json.loads(offline.stdout)
                if receipt.get("offline_geometry", {}).get("passed") is not True:
                    raise RuntimeError("Exact bundle omitted authored geometry")
                fixture = HERE / "fixtures" / suffix / "native_samples.jsonl"
                shutil.copyfile(fixture, output / fixture.name)
                positive = run_command(output / "finalize.py", "--attempt", output,
                                       "--output", output / "analysis-report.json", cwd=output)
                if positive.returncode != 0:
                    raise RuntimeError("Saved positive failed: " + positive.stdout)
                relation = json.loads((output / "analysis-report.json").read_text())["measurements"][
                    "intersection_parking_footprint"]["value"]["parking_relation"]
                expected = "outside_intersection" if suffix == "probe_a" else "within_intersection"
                if relation != expected: raise RuntimeError("Saved relation differs")
                (output / "native_samples.jsonl").unlink()
                negative = run_command(output / "finalize.py", "--attempt", output,
                                       "--output", output / "negative-report.json", cwd=output)
                if negative.returncode == 0 or "Missing required source: native_samples.jsonl" not in negative.stdout:
                    raise RuntimeError("Missing-source negative failed: " + negative.stdout)
                results.append({"case": suffix, "candidate": candidate,
                                "offline": "pass", "saved_positive": relation,
                                "saved_missing_source_negative": "pass"})
    print(json.dumps({"passed": True, "scope": "materialized exact bundle CPU diagnostics only; Core/video pending",
                      "results": results}, indent=2))


if __name__ == "__main__": main()
