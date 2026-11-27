"""Reconcile the selected CPU package with original-source limits."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / 'case-plan.json'
    plan = json.loads(path.read_text())
    for disposition in plan['requirement_dispositions']:
        disposition['evidence_or_gap'] = (
            'Twelve exact selected Native constructions have source-hashed offline, public positive and '
            'missing-source-negative, saved-only, physical/lifecycle, semantic and independent CPU audit '
            'contracts. The 100-foot district and 300-foot other-area triples, interruption, rain and '
            'signal-side contrasts are distinct. Original Native course motion, visible indicator pixels, '
            'area classification and legal judgment remain unverified.')
    for case in plan['cases']:
        case['selected'] = True
        case['planning_status'] = 'selected_cpu_prepared_original_unverified'
        case['target_type'] = 'delivery_comparison'
        case['case_description'] += '; exact selected source-bound CPU package prepared, original Native observation pending'
    for comparison in plan['comparisons']:
        suffix = comparison['comparison_id'].rsplit('__', 1)[-1]
        comparison['status'] = 'selected_cpu_audited_original_unverified'
        comparison['audit_gap'] = (
            'Independent diagnostic positive and changed-frame negative predicates pass; original '
            'Native sources, visible signal pixels, area class and statutory interpretation await review.')
        comparison['audit_script'] = 'comparison_audit.py'
        comparison['audit_script_sha256'] = sha(HERE / 'comparison_audit.py')
        comparison['positive_log'] = 'comparison-' + suffix + '-positive.log'
        comparison['positive_log_sha256'] = sha(HERE / comparison['positive_log'])
        comparison['negative_log'] = 'comparison-' + suffix + '-negative.log'
        comparison['negative_log_sha256'] = sha(HERE / comparison['negative_log'])
        comparison['audit_command'] = (
            'PYTHONPATH=runtime/scenario_pipeline .venv-cpu/bin/python -B work/' + AID +
            '/comparison_audit.py --comparison ' + comparison['comparison_id'] +
            ' --attempt $FIRST_ATTEMPT --attempt $SECOND_ATTEMPT --output $COMPARISON_OUTPUT')
    source = 'inputs/' + AID + '/assignment.json'
    for term, mapping in plan['source_observation_mapping'].items():
        mapping['evidence'] = (
            'Selected Native capture records source-bound ' + term +
            ' by original frame and saved analyzer rechecks it; public proof uses a synthetic diagnostic. '
            'Original pixels and legal interpretation remain pending.')
        mapping['channels'] = [term]
        mapping['source_refs'] = [source]
    plan['camera_plan'] = {'profile': 'overview1080-capability', 'duration_s': 30,
        'composition': 'synchronized_four_view_primary',
        'coverage': [
            {'view': 'overview', 'subject': 'full lane-change vehicle, both same-direction lanes and roadside area context',
             'interval': 'all 600 original frames'},
            {'view': 'approach', 'subject': 'observed signal onset and continuous approach path',
             'interval': 'before onset through course change'},
            {'view': 'reference_corner', 'subject': 'lane marking and full-body crossing into destination lane',
             'interval': 'approach through lane transition'},
            {'view': 'driver_reference', 'subject': 'visible indicator side, road reference and weather',
             'interval': 'signal onset through course change'}]}
    for row in plan['scope_branches']:
        row['coverage_status'] = 'selected_cpu_prepared_original_unverified'
    path.write_text(json.dumps(plan, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'cases': len(plan['cases']), 'comparisons': len(plan['comparisons']),
                      'case_plan_sha256': sha(path)}, sort_keys=True))


if __name__ == '__main__':
    main()
