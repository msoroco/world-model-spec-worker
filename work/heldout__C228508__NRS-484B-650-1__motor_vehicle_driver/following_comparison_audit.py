"""Independent source-bound audit of the two-versus-one following comparison.

This checks software evidence and comparison isolation. It cannot determine
whether the source hypotheses satisfy any cross-referenced traffic law.
"""

from hashlib import sha256
import argparse
import json
from pathlib import Path

from window_audit import audit as audit_window


PREFIX = 'heldout__C228508__NRS-484B-650-1__motor_vehicle_driver__'
HELD_CONFIG_KEYS = ('law_id', 'cell_id', 'actor', 'rate_hz', 'frames',
                    'duration_s', 'required_atoms', 'source_packets', 'cameras',
                    'engineering')
HELD_SOURCES = ('video_frames.jsonl', 'driving_trace.jsonl',
                'following_sources.jsonl')


def _read(path):
    return json.loads(Path(path).read_text())


def _hash(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def audit_pair(two_attempt, one_attempt):
    two, one = Path(two_attempt), Path(one_attempt)
    configs = [_read(root / 'config.json') for root in (two, one)]
    expected = (PREFIX + 'repeated_following', PREFIX + 'one_secondary_act')
    if tuple(c.get('selected_case_id') for c in configs) != expected:
        raise ValueError('Wrong following comparison case identities')
    if [c.get('closing_encounters') for c in configs] != [2, 1]:
        raise ValueError('Second encounter difference missing')
    for key in HELD_CONFIG_KEYS:
        if configs[0].get(key) != configs[1].get(key):
            raise ValueError('Fixed construction changed: ' + key)
    if (configs[0].get('case', {}).get('recording_description') !=
            configs[1].get('case', {}).get('recording_description')):
        raise ValueError('Fixed recording description changed')
    source_hashes = {}
    for name in HELD_SOURCES:
        a, b = _hash(two / name), _hash(one / name)
        if a != b:
            raise ValueError('Fixed original source changed: ' + name)
        source_hashes[name] = a
    reports = []
    for root in (two, one):
        receipt = audit_window(root, root / 'analysis-report.json')
        reports.append(receipt)
    if (reports[0]['candidate_window'] is None or
            reports[1]['candidate_window'] is not None):
        raise ValueError('Measured two-versus-one window difference missing')
    if _hash(two / 'event_annotations.json') == _hash(one / 'event_annotations.json'):
        raise ValueError('Declared event-source difference missing')
    return {'format': 'worker-following-comparison-source-audit',
            'comparison_id': 'two_acts_required',
            'case_ids': list(expected),
            'fixed_config_keys': list(HELD_CONFIG_KEYS),
            'fixed_source_sha256': source_hashes,
            'report_sha256': [_hash(root / 'analysis-report.json')
                              for root in (two, one)],
            'event_source_sha256': [_hash(root / 'event_annotations.json')
                                    for root in (two, one)],
            'measured_window_present': [True, False],
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


def audit_speed_pair(fast_attempt, capped_attempt):
    fast, capped = Path(fast_attempt), Path(capped_attempt)
    configs = [_read(root / 'config.json') for root in (fast, capped)]
    expected = (PREFIX + 'repeated_following', PREFIX + 'no_speed')
    if tuple(c.get('selected_case_id') for c in configs) != expected:
        raise ValueError('Wrong speed comparison case identities')
    for key in HELD_CONFIG_KEYS:
        if key != 'engineering' and configs[0].get(key) != configs[1].get(key):
            raise ValueError('Fixed construction changed: ' + key)
    engineering = [dict(c.get('engineering', {})) for c in configs]
    caps = [item.pop('requested_speed_cap_mps', 24) for item in engineering]
    if caps != [24, 13] or engineering[0] != engineering[1]:
        raise ValueError('Declared speed request difference missing or confounded')
    if [c.get('closing_encounters') for c in configs] != [2, 2]:
        raise ValueError('Fixed following encounter count changed')
    if (configs[0].get('case', {}).get('recording_description') !=
            configs[1].get('case', {}).get('recording_description')):
        raise ValueError('Fixed recording description changed')
    source_hashes = {}
    for name in HELD_SOURCES:
        a, b = _hash(fast / name), _hash(capped / name)
        if a != b:
            raise ValueError('Fixed original source changed: ' + name)
        source_hashes[name] = a
    reports = [audit_window(root, root / 'analysis-report.json')
               for root in (fast, capped)]
    if (reports[0]['candidate_window'] is None or
            reports[1]['candidate_window'] is not None):
        raise ValueError('Measured speed window difference missing')
    categories = [
        [item['category'] for item in _read(root / 'event_annotations.json')]
        for root in (fast, capped)]
    if (categories[0].count('speed') != 1 or categories[1].count('speed') != 0
            or categories[0].count('too_close') != 2
            or categories[1].count('too_close') != 2):
        raise ValueError('Declared event-source difference missing')
    return {'format': 'worker-following-comparison-source-audit',
            'comparison_id': 'speed_required', 'case_ids': list(expected),
            'fixed_config_keys': [key for key in HELD_CONFIG_KEYS if key != 'engineering'],
            'fixed_source_sha256': source_hashes,
            'report_sha256': [_hash(root / 'analysis-report.json')
                              for root in (fast, capped)],
            'event_source_sha256': [_hash(root / 'event_annotations.json')
                                    for root in (fast, capped)],
            'measured_window_present': [True, False],
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--two', required=True)
    parser.add_argument('--one', required=True)
    parser.add_argument('--comparison', choices=('two_acts_required', 'speed_required'),
                        default='two_acts_required')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError('Retain prior comparison audit receipt')
    result = (audit_pair(args.two, args.one)
              if args.comparison == 'two_acts_required'
              else audit_speed_pair(args.two, args.one))
    result['auditor_sha256'] = _hash(__file__)
    output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
