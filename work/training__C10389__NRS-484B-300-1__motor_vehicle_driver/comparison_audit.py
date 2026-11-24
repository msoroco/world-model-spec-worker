"""Compare exact device-response source records while preserving legal uncertainty."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def compare(left, right):
    a, b = (read(path) for path in (left, right))
    prefix = HERE.name + '__'
    if (a.get('case_id') != prefix + 'probe_1' or
            b.get('case_id') != prefix + 'probe_2' or
            not a.get('diagnostic_only') or not b.get('diagnostic_only') or
            a.get('accepted') or b.get('accepted')):
        raise ValueError('Exact diagnostic comparison members required')
    m = read(HERE / 'execution-manifest.json')
    if {e['case_id'] for e in m['cases']} != {a['case_id'], b['case_id']}:
        raise ValueError('Comparison differs from selected cases')
    common = {'native-map-readback.json', 'alley-stop.xodr'}
    if any(a['original_source_sha256'].get(name) != b['original_source_sha256'].get(name)
           for name in common):
        raise ValueError('Fixed device map differs')
    if a['original_source_sha256']['native-raw-actors.jsonl'] == b['original_source_sha256']['native-raw-actors.jsonl']:
        raise ValueError('Comparison has identical motion source')
    return {'format': 'c10389-device-comparison-audit-v1',
            'comparison_id': HERE.name + '__comparison',
            'case_ids': [a['case_id'], b['case_id']],
            'diagnostic_only': True, 'accepted': False,
            'fixed_map_sha256': a['original_source_sha256']['native-map-readback.json'],
            'motion_source_sha256': [a['original_source_sha256']['native-raw-actors.jsonl'],
                                     b['original_source_sha256']['native-raw-actors.jsonl']],
            'legal_verdict_claimed': False,
            'limitations': ['Original Native device authority and source pixels remain unverified.']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for option in ('left', 'right', 'output'):
        parser.add_argument('--' + option, type=Path, required=True)
    args = parser.parse_args()
    result = compare(args.left, args.right)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'comparison_id': result['comparison_id'], 'accepted': False}))
