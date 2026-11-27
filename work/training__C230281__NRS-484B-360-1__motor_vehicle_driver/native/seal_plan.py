"""Reconcile selected CPU evidence with original source-review limitations."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / 'case-plan.json'
    plan = json.loads(path.read_text())
    for case in plan['cases']:
        case['selected'] = True
        case['planning_status'] = 'selected_cpu_prepared_original_unverified'
        case['target_type'] = 'selected_delivery_comparison'
        case['recorded_value'] = None
        case['diagnostic_observed_mph'] = int(case['requested_setting'])
    for item in plan['requirement_dispositions']:
        item['evidence_or_gap'] = ('Three selected 600-frame Native constructions and source-hashed synthetic '
            'offline/public/saved speed diagnostics are prepared. Original school-bus design, judged-driver '
            'join, pupils aboard, to/from-school trip purpose, physical speed and legal judgment remain review gated.')
    for term, mapping in plan['source_observation_mapping'].items():
        mapping['evidence'] = ('Selected source-gated bus velocity and independent passenger/trip review; '
                               'synthetic diagnostic only; original fact remains unverified for ' + term)
    plan['camera_plan'] = {'profile': 'overview1080-capability', 'duration_s': 30,
        'composition': 'synchronized_four_view_primary',
        'coverage': [{'view': 'overview', 'subject': 'whole bus and road route',
                      'interval': 'frames 0-599'},
                     {'view': 'approach', 'subject': 'bus approach and velocity context',
                      'interval': 'frames 0-599'},
                     {'view': 'reference_corner', 'subject': 'bus body and surrounding road',
                      'interval': 'frames 0-599'},
                     {'view': 'driver_reference', 'subject': 'judged driver and passenger source',
                      'interval': 'frames 0-599'}]}
    plan['runtime_uncertainties'] = [
        'Original school-bus design, judged-driver identity, pupils and school-trip purpose remain source-review conditions.',
        'Synthetic diagnostic velocity and pixels do not establish original physical speed or a legal result.',
        'Accepted membership IDs have no local source-hashed equivalence receipt; no reuse is claimed.']
    comparison = plan['comparisons'][0]
    comparison['status'] = 'diagnostic_independent_audit_passed_physical_pending'
    comparison['audit'] = {'report': 'comparison-main-audit.json',
        'sha256': sha(HERE / 'comparison-main-audit.json'),
        'log': 'comparison-main-audit.log',
        'log_sha256': sha(HERE / 'comparison-main-audit.log')}
    path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + '\n')
    return {'case_plan_sha256': sha(path), 'selected_cases': 3}


if __name__ == '__main__':
    print(json.dumps(main(), sort_keys=True))
