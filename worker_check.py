"""Validate the complete full-train delivery return without CARLA."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "runtime/pipeline/scenario_pipeline"))
from worker_exchange.common import read, sha
from worker_exchange.preparation import check

batch = read(ROOT / "batch.json")
runtime = ROOT / batch["runtime"]["root"]
if sha(runtime / "SOURCE-MANIFEST.json") != batch["runtime"]["source_manifest_sha256"]:
    raise ValueError("Frozen runtime changed")

parser = argparse.ArgumentParser()
parser.add_argument("--complete", action="store_true")
parser.add_argument("--require-delivery-ready", action="store_true")
args = parser.parse_args()
result = check(ROOT, complete=args.complete or args.require_delivery_ready,
               require_ready=args.require_delivery_ready)
print(json.dumps({"batch": result["batch_id"],
                  "results": {key: value["status"] for key, value in result["results"].items()},
                  "static_validation": "passed"}, indent=2))
