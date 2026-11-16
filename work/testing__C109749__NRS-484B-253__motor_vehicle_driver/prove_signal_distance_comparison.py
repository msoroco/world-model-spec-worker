"""Compare original-shaped signal histories at fixed motion conditions."""

import copy
import hashlib
import json
from pathlib import Path

from signal_advance_audit import measure

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASES = ('signal_advance_100_below_25', 'signal_advance_100_at',
         'signal_advance_100_above_36')
TARGETS = (25.0, 30.48, 36.0)
ATTEMPTS = ('c109749-district-delivery-current-12/positive',
            'c109749-district-delivery-current-09/positive',
            'c109749-district-delivery-current-13/positive')
IDENTITY = {'selected_case_id', 'supported_case_ids', 'signal_target_m'}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def motion_without_indicator(rows):
    return [{key: value for key, value in row.items() if key != 'ego_left_indicator'}
            for row in rows]


def compare_fixed_motion(histories):
    require(len(histories) == 3 and all(len(rows) == 900 for rows in histories),
            'Three full-duration histories required')
    base = motion_without_indicator(histories[1])
    require(all(motion_without_indicator(rows) == base for rows in histories),
            'A non-signal source condition changed')


def normalized_bundle(files, case_id, target):
    """Remove only declared case identity, target, and threshold outcome."""
    result = dict(files)
    config = json.loads(result['config.json'])
    require(config['selected_case_id'] == case_id and
            config['supported_case_ids'] == [case_id] and
            config['signal_target_m'] == target,
            'Comparison case identity or signal target differs')
    result['config.json'] = json.dumps({key: value for key, value in config.items()
                                        if key not in IDENTITY}, sort_keys=True)
    runner = result['runner.py']
    exact = f"config.get('signal_target_m') != {target} or"
    require(runner.count(case_id) == 1 and runner.count(exact) == 1,
            'Declared runner target policy missing')
    error = f"Exact {target} m signal probe required"
    require(runner.count(error) == 1, 'Declared runner target error missing')
    result['runner.py'] = runner.replace(case_id, '<CASE>').replace(exact,
                               "config.get('signal_target_m') != <TARGET> or").replace(error, '<TARGET> m signal probe required')
    finalizer = result['finalizer.py']
    require(finalizer.count(case_id) == 1, 'Declared finalizer case identity missing')
    finalizer = finalizer.replace(case_id, '<CASE>')
    if target == 25.0:
        requested = "'target':'continuous_left_signal_at_least_30_48_m',\n                        'requested':False,"
        matched = "'matched':not (signal_advance['probes']['30.48']['observable_distance_met'] and signal_advance['probes']['30.48']['full_signal_onset_observed'])"
        require(finalizer.count(requested) == 1 and finalizer.count(matched) == 1,
                'Below-threshold finalizer outcome missing')
        finalizer = finalizer.replace(requested, requested.replace('False', '<TARGET_OUTCOME>'))
        finalizer = finalizer.replace(matched, "'matched':<TARGET_OUTCOME>")
    else:
        requested = "'target':'continuous_left_signal_at_least_30_48_m',\n                        'requested':True,"
        matched = "'matched':signal_advance['probes']['30.48']['observable_distance_met'] and signal_advance['probes']['30.48']['full_signal_onset_observed']"
        require(finalizer.count(requested) == 1 and finalizer.count(matched) == 1,
                'At/above-threshold finalizer outcome missing')
        finalizer = finalizer.replace(requested, requested.replace('True', '<TARGET_OUTCOME>'))
        finalizer = finalizer.replace(matched, "'matched':<TARGET_OUTCOME>")
    result['finalizer.py'] = finalizer
    return result


def compare_fixed_construction(bundles):
    require(len(bundles) == 3, 'Three selected constructions required')
    normalized = [normalized_bundle(files, ROOT.name + '__' + name, target)
                  for files, name, target in zip(bundles, CASES, TARGETS)]
    require(normalized[0] == normalized[1] == normalized[2],
            'Construction differs outside declared signal target')


def main():
    histories = []
    evidence = []
    bundles = []
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    for name, target, attempt_name in zip(CASES, TARGETS, ATTEMPTS):
        case_id = ROOT.name + '__' + name
        selected = next(c for c in manifest['cases'] if c['case_id'] == case_id)
        construction = ROOT / selected['construction']
        require(hashlib.sha256(construction.read_bytes()).hexdigest() == selected['construction_sha256'],
                'Selected comparison construction changed')
        bundle = json.loads(construction.read_text())
        files = {f['path']: f['content'] for f in bundle['files']}
        bundles.append(files)
        config = json.loads(files['config.json'])
        require(config['signal_target_m'] == target, 'Selected signal target changed')
        attempt = REPO / '.runtime-work' / attempt_name / 'attempt'
        source = attempt / 'interaction_history.jsonl'
        source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
        seal = json.loads((attempt / 'capture-seal.json').read_text())
        audit_path = attempt / 'diagnostic-audit.json'
        audit = json.loads(audit_path.read_text())
        require(seal['sources']['interaction_history.jsonl'] == source_hash and
                audit['original_sources']['history_sha256'] == source_hash and
                audit['case_id'] == case_id and audit['frames'] == 900 and
                audit['software_checks_passed'] is True and audit['passed'] is False and
                audit['physical_acceptance_claimed'] is False,
                'Sealed diagnostic delivery source differs')
        rows = [json.loads(line) for line in source.read_text().splitlines() if line]
        require(len(rows) == 900, 'Comparison needs all 900 sealed frames')
        observed = measure(rows)
        value = observed['observed_continuous_approach_distance_m']
        require(abs(value - target) < .05 and
                observed['probes']['30.48']['observable_distance_met'] == (target >= 30.48)
                and observed['probes']['30.48']['full_signal_onset_observed'] is True
                and observed['legal_verdict_asserted'] is False,
                'Source-measured boundary result differs')
        histories.append(rows)
        evidence.append({'case_id': case_id,
                         'construction_sha256': selected['construction_sha256'],
                         'source_sha256': source_hash,
                         'diagnostic_audit_sha256': hashlib.sha256(audit_path.read_bytes()).hexdigest(),
                         'authored_target_m': target, 'measured_m': value,
                         'continuous_start_frame': observed['continuous_start_frame'],
                         'observable_30_48_m_met': target >= 30.48})
    compare_fixed_construction(bundles)
    compare_fixed_motion(histories)
    require(all(left['measured_m'] < right['measured_m']
                for left, right in zip(evidence, evidence[1:])),
            'Observed signal onset does not increase across probes')
    mutated = copy.deepcopy(histories[0])
    mutated[80]['oncoming']['position_xy_m'][0] += 1.0
    try:
        compare_fixed_motion((mutated, histories[1], histories[2]))
    except ValueError as error:
        if 'non-signal source condition changed' not in str(error):
            raise
    else:
        raise ValueError('Changed opposing position passed fixed-condition check')
    print(json.dumps({'format': 'worker-signal-distance-fixed-condition-comparison',
                      'cases': evidence, 'fixed_motion_except_indicator': True,
                      'fixed_construction_except_declared_target': True,
                      'changed_opposing_position_rejected': True,
                      'frames': 900,
                      'source_kind': 'sealed synthetic software delivery diagnostics',
                      'native_or_legal_acceptance_claimed': False}, indent=2))


if __name__ == '__main__':
    main()
