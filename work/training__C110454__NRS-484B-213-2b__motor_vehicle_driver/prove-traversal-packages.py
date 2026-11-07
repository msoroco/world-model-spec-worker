"""Pinned exact offline and synthetic v1 package probes for traversal bundles."""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(ROOT / "runtime/pipeline/scenario_pipeline"))
spec=importlib.util.spec_from_file_location("probe_core_traversal",HERE / "probe-core-traversal.py")
fixture=importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
make_attempt=fixture.make_attempt
from worker_exchange.package_compatibility import run, materialize_case
from worker_exchange.runtime_cli import execution_env

CASES=("traversal_reference","traversal_contrast")
CANDIDATES=("primary","fallback1","fallback2","fallback3")
MANIFEST=HERE / "draft-traversal-execution-manifest.json"
PYTHON=ROOT / ".venv-cpu/bin/python"


def prove(suffix):
    if suffix not in CASES: raise ValueError("Unknown traversal case")
    case=HERE.name+"__"+suffix
    scratch=Path(tempfile.mkdtemp(prefix="c110454-traversal-exact-",dir=ROOT / ".runtime-work"))
    source=scratch / "fixture"
    make_attempt(source,suffix,full_resolution=True)
    (source / "config.json").unlink()
    outcomes=[]
    for candidate in CANDIDATES:
        folder=HERE / "draft-traversal-candidates" / suffix / candidate
        offline_dir=scratch / ("offline-"+candidate)
        command=[str(PYTHON),str(ROOT / "runtime.py"),"offline","--manifest",str(MANIFEST),
                 "--case",case,"--candidate",candidate,"--output",str(offline_dir),
                 "--python",str(PYTHON)]
        offline=subprocess.run(command,cwd=ROOT,env=os.environ.copy(),text=True,
                               stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
        if offline.returncode:
            raise RuntimeError(f"{suffix}/{candidate} offline failed: {offline.stdout}")
        shutil.copy2(offline_dir / "offline.log",folder / "offline.log")
        (folder / "command-offline.log").write_text(offline.stdout)
        output=scratch / ("output-"+candidate)
        receipt=run(MANIFEST,case,source,output,ROOT / "runtime/pipeline/library",
                    ROOT / ".runtime-work/decoder-refresh-20261105/.lake/build/bin/adapterCheck",candidate)
        negative=scratch / ("negative-"+candidate)
        materialize_case(MANIFEST,case,negative,source,candidate)
        (negative / "native_samples.jsonl").unlink()
        failed=subprocess.run([str(PYTHON),str(negative / "finalize.py"),"--attempt",str(negative),
                               "--output",str(negative / "analysis-report.json")],
                              cwd=negative,env=execution_env(),text=True,
                              stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=300)
        expected="Missing required source: native_samples.jsonl"
        if failed.returncode==0 or expected not in failed.stdout:
            raise RuntimeError(f"{suffix}/{candidate} missing-source negative failed: {failed.stdout}")
        shutil.copy2(output / "compatibility.json",folder / "diagnostic-compatibility.json")
        shutil.copy2(output / "compatibility-analysis.log",folder / "analysis-compatibility.log")
        (folder / "negative-analysis.log").write_text(failed.stdout)
        (folder / "compatibility.log").write_text(json.dumps({"positive_passed":receipt["passed"],
             "checks":receipt["checks"],"negative_exit_code":failed.returncode,
             "negative_expected_error":expected,"synthetic_diagnostic":True},indent=2)+"\n")
        outcomes.append({"candidate":candidate,"construction_sha256":receipt["construction_sha256"],
                         "offline_passed":True,"compatibility_passed":receipt["passed"],
                         "negative_exit_code":failed.returncode})
        print(suffix,candidate,"offline and v1 package passed",flush=True)
    return {"suffix":suffix,"scratch":str(scratch),"outcomes":outcomes}


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--suffix",choices=CASES,required=True)
    args=parser.parse_args()
    print(json.dumps(prove(args.suffix),indent=2))
