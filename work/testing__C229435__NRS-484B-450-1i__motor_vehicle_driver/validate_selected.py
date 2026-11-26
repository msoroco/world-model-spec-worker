"""Recheck all selected C228096 CPU receipt bindings and runtime validators."""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.execution_manifest import validate as validate_manifest
from worker_exchange.semantic_delivery import validate as validate_semantic
from worker_exchange.delivery_handoff import validate_case
from worker_exchange.package_compatibility import check_receipts


def read(name: str):
    return json.loads((ROOT / name).read_text())


def main() -> None:
    original = json.loads((REPO / 'inputs' / ROOT.name / 'assignment.json').read_text())
    manifest = validate_manifest(REPO, ROOT.name)
    semantic = validate_semantic(ROOT, original, manifest)
    for entry in manifest['cases']:
        validate_case(ROOT, entry, original.get('selection_targets'))
    check_receipts(REPO, ROOT, manifest)
    offline = read('cpu-offline-proofs.json')
    compatibility = read('cpu-compatibility-proofs.json')
    saved = read('cpu-saved-proofs.json')
    independent = read('cpu-independent-proofs.json')
    comparisons = read('cpu-comparison-proofs.json')
    if (len(manifest['cases']), len(offline), len(compatibility), len(saved),
            len(independent), len(comparisons)) != (4, 8, 8, 4, 4, 3):
        raise ValueError('selected proof counts differ')
    if any(row['exit_code'] for row in offline + compatibility + saved):
        raise ValueError('offline, compatibility or saved-only proof failed')
    if any(row['positive_exit_code'] or row['negative_exit_code'] == 0
            for row in independent):
        raise ValueError('independent source audit positive/negative differs')
    if any(row['exit_code'] for row in comparisons):
        raise ValueError('saved comparison proof failed')
    print(json.dumps({'selected_cases': 4, 'offline_candidates': 8,
        'compatibility_candidates': 8, 'saved_only_cases': 4,
        'independent_delivery_pairs': 4, 'comparisons': 3,
        'semantic_stages': semantic['stage_count'], 'runtime_validators': 'passed'},
        sort_keys=True))


if __name__ == '__main__':
    main()
