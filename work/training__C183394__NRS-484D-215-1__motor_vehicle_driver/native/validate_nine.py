"""Run the pinned exact-case CPU validators for this assignment."""
import json
from pathlib import Path

from worker_exchange.execution_manifest import validate as validate_manifest
from worker_exchange.package_compatibility import check_receipts
from worker_exchange.semantic_delivery import validate as validate_semantic
from worker_exchange.delivery_handoff import validate_case


ROOT = Path(__file__).resolve().parents[3]
FOLDER = Path(__file__).resolve().parents[1]
AID = FOLDER.name
original = json.loads((ROOT / 'inputs' / AID / 'assignment.json').read_text())
manifest = validate_manifest(ROOT, AID)
assert len(manifest['cases']) == 9
print('PASS execution manifest 9')
check_receipts(ROOT, FOLDER, manifest)
print('PASS compatibility 9')
validate_semantic(FOLDER, original, manifest)
print('PASS semantic 9')
for entry in manifest['cases']:
    validate_case(FOLDER, entry, original.get('selection_targets'))
print('PASS handoff 9')
