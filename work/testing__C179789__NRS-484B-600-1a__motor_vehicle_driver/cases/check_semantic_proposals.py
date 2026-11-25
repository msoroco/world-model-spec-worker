"""Run canonical stage validation against all six exact constructions."""
import json
from pathlib import Path
from worker_exchange.semantic_delivery import validate

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
ASSIGNMENT = 'testing__C179789__NRS-484B-600-1a__motor_vehicle_driver'
original = json.loads((REPO / 'inputs' / ASSIGNMENT / 'assignment.json').read_text())
suffixes = ('dry_open_traffic', 'wet_same_traffic', 'narrow_same_traffic',
            'dense_traffic', 'low_visibility', 'ice_or_snow')
manifest = {'cases': [{'case_id': ASSIGNMENT + '__' + suffix,
                       'construction': 'construction.json' if suffix == 'dry_open_traffic' else
                       'cases/' + suffix + '-construction.json'} for suffix in suffixes]}
print(json.dumps(validate(ROOT, original, manifest), indent=2))
