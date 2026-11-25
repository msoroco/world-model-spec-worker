"""Validate the seven draft semantic cases against diagnostic constructions."""
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
output_root = Path(os.environ['SCENARIO_PIPELINE_OUTPUT_ROOT']).resolve()
if ROOT / '.runtime-work' not in output_root.parents:
    raise ValueError('Pipeline output must remain under .runtime-work')
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from worker_exchange.semantic_delivery import validate  # noqa: E402

assignment = json.loads((ROOT / 'inputs' / HERE.name / 'assignment.json').read_text())
manifest = json.loads((HERE / 'execution-manifest.compatibility-diagnostic.json').read_text())
print(json.dumps(validate(HERE, assignment, manifest), indent=2))
