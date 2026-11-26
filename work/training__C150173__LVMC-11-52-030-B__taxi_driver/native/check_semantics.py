"""Check the taxi stage chain against the pinned runtime without local adoption."""
import json
import sys
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent.parent
ROOT = PACKAGE.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from worker_exchange.semantic_delivery import validate  # noqa: E402


if __name__ == '__main__':
    assignment = json.loads((ROOT / 'inputs' / PACKAGE.name / 'assignment.json').read_text())
    manifest = json.loads((PACKAGE / 'selected-draft-manifest.json').read_text())
    print(json.dumps(validate(PACKAGE, assignment, manifest), sort_keys=True))
