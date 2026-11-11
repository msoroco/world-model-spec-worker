"""Compare signalled and omitted-signal turns from sealed original sources.

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


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def original(root):
    root = Path(root)
    seal = json.loads((root / 'capture-seal.json').read_text())
    audit = json.loads((root / 'diagnostic-audit.json').read_text())
    if (audit.get('software_checks_passed') is not True or audit.get('passed') is not False
            or audit.get('diagnostic_fixture') is not True or audit.get('frames') != 900):
        raise ValueError('Full-duration diagnostic delivery audit missing')
    for name in SOURCES:
        if seal.get('sources', {}).get(name) != sha(root / name):
            raise ValueError('Sealed comparison source changed: ' + name)
    if audit['original_sources']['history_sha256'] != sha(root / 'interaction_history.jsonl'):
        raise ValueError('Comparison source differs from delivery audit')
    return [json.loads(line) for line in (root / 'interaction_history.jsonl').read_text().splitlines() if line]


def compare(signalled, omitted):
    signalled, omitted = Path(signalled), Path(omitted)
    left, right = original(signalled), original(omitted)
    if len(left) != 900 or len(right) != 900:
        raise ValueError('Full-duration paired originals required')
    for name in ('intersection_geometry.json', 'video_frames.jsonl'):
        if (signalled / name).read_bytes() != (omitted / name).read_bytes():
            raise ValueError('Fixed source differs: ' + name)
    for index, (a, b) in enumerate(zip(left, right)):
        if a['frame'] != b['frame'] or a['time_s'] != b['time_s']:
            raise ValueError('Paired frame/time differs')
        for field in a.keys() | b.keys():
            if field != 'ego_left_indicator' and a.get(field) != b.get(field):
                raise ValueError('Fixed original field differs: ' + field)
        if b['ego_left_indicator'] is not False:
            raise ValueError('Omitted branch has left indicator at frame ' + str(index))
    configs = [json.loads((ROOT / 'cases' / name / 'config.json').read_text())
               for name in ('inside_yield', 'signal_omitted')]
    for field in set(configs[0]) & set(configs[1]):
        if field not in ('selected_case_id', 'supported_case_ids') and configs[0][field] != configs[1][field]:
            raise ValueError('Fixed construction config differs: ' + field)
    a, b = observe_signalled(signalled), observe_omitted(omitted)
    for field in ('subject_yield_frames', 'initial_oncoming_clearance_frame', 'ego_turn_start_frame'):
        if a[field] != b[field]:
            raise ValueError('Fixed yield/turn observation differs: ' + field)
    return {'format': 'c109749-signal-comparison-diagnostic',
            'software_checks_passed': True, 'diagnostic_fixture': True,
            'delivery_passed': False, 'physical_acceptance_claimed': False,
            'legal_verdict_asserted': False, 'fixed_samples': 900,
            'declared_difference': 'left indicator readback',
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
