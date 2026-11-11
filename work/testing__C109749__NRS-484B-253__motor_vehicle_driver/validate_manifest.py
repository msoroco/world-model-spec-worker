"""Validate the current canonical exact-case manifest with pinned runtime."""
import json
import sys
from pathlib import Path

folder = Path(__file__).resolve().parent
repo = folder.parent.parent
sys.path.insert(0, str(repo / 'runtime/scenario_pipeline'))
from worker_exchange.execution_manifest import validate

manifest = validate(repo, folder.name)
print(json.dumps({'assignment_id': folder.name,
                  'validated_case_ids': [case['case_id'] for case in manifest['cases']],
                  'cpu_manifest_passed': True}))
