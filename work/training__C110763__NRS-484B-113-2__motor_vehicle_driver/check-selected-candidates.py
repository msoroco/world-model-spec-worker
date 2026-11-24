"""Check all selected CPU construction identities and candidate receipts."""
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

from worker_exchange.candidate_constructions import validate

folder = Path(__file__).resolve().parent
manifest = json.loads((folder / "execution-manifest.json").read_text())
for entry in manifest["cases"]:
    print(validate(folder, entry, "NRS-484B-113-2", "C110763", required=True,
                   require_alternate=True, candidate_count=4))
