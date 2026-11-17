"""Exercise all planned C150142 comparison branches with diagnostic sources."""
import copy
import hashlib
import json
import tempfile
from pathlib import Path

from comparison_audit import audit


ROOT = Path(__file__).resolve().parents[1]
PLAN = json.loads((ROOT / 'case-plan.json').read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def difference_value(name, position, count):
    if name == 'stationary_duration_s':
        return [1799.95, 1800, 1800.05][position]
    if name in ('sign_present', 'red_curb_stop_or_park',
                'passenger_loading_event', 'business_activity_event',
                'mailbox_presence', 'mail_deposit_event'):
        return position == 1 if count == 2 else position > 0
    raise ValueError('Unimplemented difference: ' + name)


def build(root, comparison):
    result = {'format': 'c150142-source-comparison-v1',
              'comparison_id': comparison['comparison_id'], 'cases': {}}
    fixed = comparison['fixed_conditions']
    varied = comparison['deliberate_differences']
    for position, case_id in enumerate(comparison['case_ids']):
        data = {name: 'C150142' if name == 'cell' else
                'motor_vehicle_driver' if name == 'actor' else
                'shared-diagnostic-' + name for name in fixed}
        data.update({name: difference_value(name, position,
                                             len(comparison['case_ids']))
                     for name in varied})
        source = root / ('source-' + str(position) + '.json')
        source.write_text(json.dumps({'case_id': case_id,
                                      'source_kind': 'synthetic_native_sample',
                                      'facts': data}, sort_keys=True))
        result['cases'][case_id] = {
            'source_kind': 'synthetic_native_sample',
            'facts': {name: {'path': source.name, 'sha256': digest(source),
                             'pointer': '/facts/' + name.replace('~', '~0').replace('/', '~1')}
                      for name in data}}
    return result


def expect_rejection(plan, bundle, root, comparison_id, message, synthetic=True):
    try:
        audit(plan, bundle, root, comparison_id, synthetic)
    except ValueError as error:
        if message not in str(error):
            raise AssertionError(f'wrong rejection: {error}') from error
        return
    raise AssertionError('comparison audit accepted ' + message)


def main():
    passed = []
    with tempfile.TemporaryDirectory(prefix='c150142-comparison-', dir='.runtime-work') as tmp:
        root = Path(tmp)
        for index, comparison in enumerate(PLAN['comparisons']):
            folder = root / str(index)
            folder.mkdir()
            bundle = build(folder, comparison)
            result = audit(PLAN, bundle, folder, comparison['comparison_id'], True)
            assert result['physical_acceptance_claimed'] is False
            passed.append(comparison['comparison_id'])
            if index == 0:
                expect_rejection(PLAN, bundle, folder, comparison['comparison_id'],
                                 'original Native provenance', False)
                changed = copy.deepcopy(bundle)
                second = comparison['case_ids'][1]
                changed['cases'][second]['facts']['weather']['path'] = '../source-0.json'
                expect_rejection(PLAN, changed, folder, comparison['comparison_id'],
                                 'Unsafe fact path')
                changed = copy.deepcopy(bundle)
                changed['cases'][second]['facts']['weather']['path'] = 'source-0.json'
                changed['cases'][second]['facts']['weather']['sha256'] = digest(folder / 'source-0.json')
                expect_rejection(PLAN, changed, folder, comparison['comparison_id'],
                                 'identity/provenance mismatch')
                changed = copy.deepcopy(bundle)
                source = folder / 'source-1.json'
                raw = json.loads(source.read_text())
                raw['facts']['weather'] = 'changed-weather'
                source.write_text(json.dumps(raw))
                expect_rejection(PLAN, changed, folder, comparison['comparison_id'],
                                 'Stale fact source')
                for binding in changed['cases'][second]['facts'].values():
                    binding['sha256'] = digest(source)
                expect_rejection(PLAN, changed, folder, comparison['comparison_id'],
                                 'Fixed condition changed: weather')
                raw['facts'].pop('weather')
                source.write_text(json.dumps(raw))
                for binding in changed['cases'][second]['facts'].values():
                    binding['sha256'] = digest(source)
                expect_rejection(PLAN, changed, folder, comparison['comparison_id'],
                                 'Missing source fact')
            if comparison['deliberate_differences'] == ['stationary_duration_s']:
                source = folder / 'source-1.json'
                raw = json.loads(source.read_text())
                raw['facts']['stationary_duration_s'] = 1800.05
                source.write_text(json.dumps(raw))
                for binding in bundle['cases'][comparison['case_ids'][1]]['facts'].values():
                    binding['sha256'] = digest(source)
                expect_rejection(PLAN, bundle, folder, comparison['comparison_id'],
                                 '30-minute boundary observations')
    print(json.dumps({'format': 'c150142-comparison-audit-diagnostics-v1',
                      'comparisons_passed': len(passed),
                      'comparison_ids': passed,
                      'negative_checks': ['synthetic_provenance_rejected_without_flag',
                                          'unsafe_path', 'wrong_case_source',
                                          'stale_source', 'changed_fixed_weather',
                                          'missing_source_fact',
                                          'wrong_30_minute_boundary'],
                      'physical_acceptance_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
