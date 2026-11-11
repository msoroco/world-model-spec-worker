"""Compare matched 30.48 m signalled and omitted turns from sealed originals.

The diagnostic result is a software check, never physical or legal acceptance.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

from inside_yield_observation import observe as observe_signalled
from signal_omitted_observation import observe as observe_omitted

ROOT = Path(__file__).resolve().parent
SOURCES = ('intersection_geometry.json', 'interaction_history.jsonl', 'video_frames.jsonl')
SIGNED = ROOT.name + '__signal_advance_100_at'
OMITTED = ROOT.name + '__signal_advance_100_omitted'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def original(root, case):
    root = Path(root)
    seal = json.loads((root / 'capture-seal.json').read_text())
    audit = json.loads((root / 'diagnostic-audit.json').read_text())
    if (audit.get('case_id') != case or audit.get('software_checks_passed') is not True or audit.get('passed') is not False
            or audit.get('diagnostic_fixture') is not True or audit.get('frames') != 900):
        raise ValueError('Full-duration diagnostic delivery audit missing')
    for name in SOURCES:
        if seal.get('sources', {}).get(name) != sha(root / name):
            raise ValueError('Sealed comparison source changed: ' + name)
    if audit['original_sources']['history_sha256'] != sha(root / 'interaction_history.jsonl'):
        raise ValueError('Comparison source differs from delivery audit')
    return ([json.loads(line) for line in (root / 'interaction_history.jsonl').read_text().splitlines() if line], audit)


def compare_rows(left, right):
    if len(left) != 900 or len(right) != 900:
        raise ValueError('Full-duration paired originals required')
    observed = 0
    for index, (a, b) in enumerate(zip(left, right)):
        if a['frame'] != b['frame'] or a['time_s'] != b['time_s']:
            raise ValueError('Paired frame/time differs')
        for field in a.keys() | b.keys():
            if field != 'ego_left_indicator' and a.get(field) != b.get(field):
                raise ValueError('Fixed original field differs: ' + field)
        if b['ego_left_indicator'] is not False:
            raise ValueError('Omitted branch has left indicator at frame ' + str(index))
        observed += bool(a['ego_left_indicator'])
    if not observed:
        raise ValueError('Signalled branch contains no observed left indication')
    return observed


def fixed_config(value):
    if isinstance(value, dict):
        return {key: fixed_config(item) for key, item in value.items()
                if key not in ('selected_case_id', 'supported_case_ids', 'left_signal_enabled')}
    if isinstance(value, list):
        return [fixed_config(item) for item in value]
    return value


def compare(signalled, omitted):
    signalled, omitted = Path(signalled), Path(omitted)
    left, signalled_audit = original(signalled, SIGNED)
    right, omitted_audit = original(omitted, OMITTED)
    for name in ('intersection_geometry.json', 'video_frames.jsonl'):
        if (signalled / name).read_bytes() != (omitted / name).read_bytes():
            raise ValueError('Fixed source differs: ' + name)
    signalled_frames = compare_rows(left, right)
    configs = [json.loads((ROOT / 'cases' / name / 'config.json').read_text())
               for name in ('signal_advance_100_at', 'signal_advance_100_omitted')]
    if (configs[0]['selected_case_id'] != SIGNED or configs[1]['selected_case_id'] != OMITTED or
            configs[0]['left_signal_enabled'] is not True or configs[1]['left_signal_enabled'] is not False):
        raise ValueError('Paired exact case or declared indicator difference missing')
    if fixed_config(configs[0]) != fixed_config(configs[1]):
        raise ValueError('Fixed construction config differs')
    if (signalled_audit.get('signal_advance', {}).get('observable_30_48_m_met') is not True or
            omitted_audit.get('signal_sequence', {}).get('ego_left_indicator_frames') != []):
        raise ValueError('Paired delivery audits do not establish signal contrast')
    a, b = observe_signalled(signalled), observe_omitted(omitted)
    for field in ('subject_yield_frames', 'initial_oncoming_clearance_frame', 'ego_turn_start_frame'):
        if a[field] != b[field]:
            raise ValueError('Fixed yield/turn observation differs: ' + field)
    return {'format': 'c109749-signal-comparison-diagnostic',
            'software_checks_passed': True, 'diagnostic_fixture': True,
            'delivery_passed': False, 'physical_acceptance_claimed': False,
            'legal_verdict_asserted': False, 'fixed_samples': 900,
            'declared_difference': 'left indicator readback',
            'signalled_indicator_frames': signalled_frames,
            'observed_continuous_approach_distance_m': signalled_audit['signal_advance']['observed_continuous_approach_distance_m'],
            'signalled_case_id': configs[0]['selected_case_id'],
            'omitted_case_id': configs[1]['selected_case_id'],
            'signalled_source_sha256': sha(signalled / 'interaction_history.jsonl'),
            'omitted_source_sha256': sha(omitted / 'interaction_history.jsonl'),
            'signalled_turn_frame': a['ego_turn_start_frame'],
            'omitted_turn_frame': b['ego_turn_start_frame']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--signalled', type=Path, required=True)
    parser.add_argument('--omitted', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.signalled, args.omitted)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
