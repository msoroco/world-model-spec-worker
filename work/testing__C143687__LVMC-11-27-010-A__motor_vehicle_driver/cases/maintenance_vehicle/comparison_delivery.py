"""Source-bound, saved-only controlled comparisons for C143687.

This checks original attempt integrity and the declared comparison variable.
It does not infer statutory sufficiency or physical video visibility.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent


def _load(name: str):
    spec = importlib.util.spec_from_file_location('c143687_' + name, ROOT / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


delivery = _load('delivery_audit')
saved = _load('saved_audit')
COMPARISONS = {
    'trail_not_designated': ('not_designated', 'official_plan_designation'),
    'trail_not_dedicated': ('not_dedicated', 'city_trail_dedication'),
    'trail_no_prohibition_sign': ('no_prohibition_sign', 'prohibits_motor_vehicles'),
    'trail_emergency_vehicle': ('emergency_vehicle', 'emergency_use'),
    'trail_maintenance_vehicle': ('maintenance_vehicle', 'maintenance_use'),
}


def audit_comparison(comparison_id: str, baseline: Path, variant: Path) -> dict:
    if comparison_id not in COMPARISONS:
        raise ValueError('unknown exact comparison')
    suffix, difference = COMPARISONS[comparison_id]
    roots = [Path(baseline).resolve(), Path(variant).resolve()]
    if roots[0] == roots[1]:
        raise ValueError('comparison needs two distinct saved attempts')
    expected = [saved.ASSIGNMENT_ID + '__all_prerequisites',
                saved.ASSIGNMENT_ID + '__' + suffix]
    summaries = []
    acquisitions = []
    for root, case_id in zip(roots, expected):
        inventory = root / 'acquisition.json'
        acquisition = json.loads(inventory.read_text(encoding='utf-8'))
        if acquisition.get('provenance_kind') != 'original_native' or acquisition.get('diagnostic_fixture') is not False:
            raise ValueError('comparison original acquisition provenance missing')
        source = delivery.audit_saved(root, inventory, case_id)
        if not source['native_source'] or not source['all_participants'] or not source['time_join']:
            raise ValueError('comparison source audit incomplete')
        history = root / acquisition['history']['path']
        summaries.append(saved.audit_history(history, acquisition['history']['sha256'], case_id))
        acquisitions.append(source['acquisition_sha256'])
    if acquisitions[0] == acquisitions[1]:
        raise ValueError('comparison reuses one acquisition source')
    paired = saved.audit_pair(summaries[0], summaries[1], difference)
    return {'format': 'worker-comparison-source-audit', 'comparison_id': comparison_id,
            'case_ids': expected, 'attempts': [str(root) for root in roots],
            'acquisition_sha256': acquisitions,
            'original_history_sha256': paired['source_hashes'],
            'fixed_conditions_checked': list(saved.FIXED) +
                [key for key in saved.CONDITIONS if key != difference],
            'deliberate_difference': difference, 'native_source': True,
            'physical_video_visibility_verified': False, 'legal_judgment': None}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True, choices=sorted(COMPARISONS))
    parser.add_argument('--baseline', required=True)
    parser.add_argument('--variant', required=True)
    args = parser.parse_args()
    print(json.dumps(audit_comparison(args.comparison, args.baseline, args.variant),
                     sort_keys=True))


if __name__ == '__main__':
    main()
