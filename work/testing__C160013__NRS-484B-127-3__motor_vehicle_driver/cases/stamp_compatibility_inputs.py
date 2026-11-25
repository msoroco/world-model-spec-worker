"""Bind diagnostic recipes to the selected, already-offline-proved cases."""
import json
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
manifest_path = PACKAGE / 'execution-manifest.json'
manifest = json.loads(manifest_path.read_text())
cases = []
for entry in manifest['cases']:
    label = 'wide' if entry['case_id'].endswith('__entrant_can_occupy_gap') else 'narrow'
    entry['fixture_recipe'] = 'work/' + PACKAGE.name + '/cases/' + label + '-recipe.json'
    construction = json.loads((PACKAGE / entry['construction']).read_text())
    cases.append({'case_id': entry['case_id'], 'target_law_id': 'NRS-484B-127-3',
                  'target_type': 'diagnostic',
                  'rationale': 'Original-source CPU compatibility for selected caravan gap outcome.',
                  'variable_assignments': {}, 'unresolved_judgment_calls': [
                      'Actual district and caravan status and without-danger judgment need Native source review.'],
                  'recording_description': construction['recording_description']})
proposal_path = PACKAGE / 'proposals/cases.json'
proposal_path.parent.mkdir(parents=True, exist_ok=True)
proposal_path.write_text(json.dumps({'cell_id': 'C160013', 'actor': 'motor_vehicle_driver',
                                     'status': 'draft', 'cases': cases,
                                     'sweep_specs': [], 'sweeps_expanded': []}, indent=2) + '\n')
manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
