"""Revalidate retained primary compatibility receipts against current sources."""
import json
import os
import sys
from pathlib import Path


repo = Path(__file__).resolve().parents[2]
runtime = repo / "runtime" / "pipeline"
output = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
assert repo / ".runtime-work" in output.parents
sys.path.insert(0, str(runtime / "scenario_pipeline"))
sys.path.insert(1, str(runtime / "python"))

from worker_exchange.package_compatibility import check_receipts

folder = Path(__file__).resolve().parent
manifest = json.loads((folder / "execution-manifest.json").read_text())
check_receipts(repo, folder, manifest)
print("selected primary compatibility receipt checks passed for both cases")
