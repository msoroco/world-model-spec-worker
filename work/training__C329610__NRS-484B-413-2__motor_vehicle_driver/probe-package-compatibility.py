"""One exact unselected v1 package positive and removed-source negative."""
import importlib.util
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
sys.path.insert(0, str(REPO / "runtime/pipeline/scenario_pipeline"))
spec = importlib.util.spec_from_file_location("core_fixture", HERE / "probe-core-synthetic.py")
core_fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(core_fixture)
from worker_exchange.package_compatibility import run, materialize_case
from worker_exchange.runtime_cli import execution_env


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--suffix",choices=("below_100_ft","at_100_ft","above_100_ft",
                                           "below_300_ft","at_300_ft","above_300_ft"),default="at_100_ft")
    parser.add_argument("--candidate",choices=("primary","fallback1","fallback2","fallback3"),default="primary")
    parser.add_argument("--full-resolution",action="store_true")
    args=parser.parse_args()
    suffix = args.suffix
    candidate = args.candidate
    scratch = Path(tempfile.mkdtemp(dir=REPO / ".runtime-work", prefix="c329610-413-v1-"))
    source = scratch / "source"
    fixture_root="c329610-413-saved-fixtures-full" if args.full_resolution else "c329610-413-saved-fixtures"
    shutil.copytree(REPO / ".runtime-work" / fixture_root / (suffix + "-source"), source)
    core_fixture.enrich(source)
    (source / "config.json").unlink()
    print("scratch", scratch, flush=True)
    manifest = HERE / "draft-execution-manifest.json"
    case = HERE.name + "__" + suffix
    receipt = run(manifest, case, source, scratch / "output", REPO / "runtime/pipeline/library",
                  REPO / ".runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck", candidate)
    negative = scratch / "negative"
    materialize_case(manifest, case, negative, source, candidate)
    (negative / "native_samples.jsonl").unlink()
    bad = subprocess.run([sys.executable, str(negative / "finalize.py"), "--attempt", str(negative),
        "--output", str(negative / "analysis-report.json")], cwd=negative, env=execution_env(),
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=300)
    (scratch / "negative-analysis.log").write_text(bad.stdout)
    if bad.returncode == 0 or "Missing required source: native_samples.jsonl" not in bad.stdout:
        raise RuntimeError("Removed-source negative failed: " + bad.stdout[-1000:])
    print(json.dumps({"case_id":case,"candidate_id":candidate,
        "positive":{k:v for k,v in receipt.items() if k != "fixture_manifest"},
        "negative":{"exit_code":bad.returncode,"removed":"native_samples.jsonl"},
        "synthetic":True,"selected":False,"original_pixels":False}))


if __name__ == "__main__":
    main()
