"""Revalidate the eight selected source-gated CPU packages."""
import json
from pathlib import Path

from worker_exchange.delivery_handoff import validate_case
from worker_exchange.execution_manifest import validate
from worker_exchange.package_compatibility import check_receipts
from worker_exchange.semantic_delivery import validate as validate_semantic

ROOT = Path(__file__).resolve().parents[2]
FOLDER = Path(__file__).resolve().parent
ASSIGNMENT = FOLDER.name


def main():
    original = json.loads((ROOT / 'inputs' / ASSIGNMENT / 'assignment.json').read_text())
    manifest = validate(ROOT, ASSIGNMENT)
    semantic = validate_semantic(FOLDER, original, manifest)
    for entry in manifest['cases']:
        validate_case(FOLDER, entry, original.get('selection_targets'))
    check_receipts(ROOT, FOLDER, manifest)
    print(json.dumps({'execution_cases': len(manifest['cases']),
                      'semantic_selected_cases': semantic['selected_cases'],
                      'delivery_cases': len(manifest['cases']),
                      'compatibility_cases': len(manifest['cases']),
                      'passed': True}, sort_keys=True))


if __name__ == '__main__':
    main()
