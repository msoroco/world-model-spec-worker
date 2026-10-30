"""Run the single frozen portable runtime in this worker checkout."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "runtime/pipeline/scenario_pipeline"))
sys.path.insert(1, str(ROOT / "runtime/pipeline/python"))

from worker_exchange.common import read, sha
from worker_exchange.runtime_cli import main

batch = read(ROOT / "batch.json")
runtime = ROOT / batch["runtime"]["root"]
if sha(runtime / "SOURCE-MANIFEST.json") != batch["runtime"]["source_manifest_sha256"]:
    raise ValueError("Frozen runtime changed")

if __name__ == "__main__":
    main()
