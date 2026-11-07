"""Case-specific saved C405647 motion analysis; no legal or physical verdict."""
import argparse
import hashlib
import json
from pathlib import Path

from measure_saved import measure

SOURCES = ('source-scope.json', 'actor-frames.jsonl')


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def approach_clearance_and_lamp_timing(folder):
    return measure(folder)


def analysis_report(folder):
    folder = Path(folder)
    for name in SOURCES:
        if not (folder / name).is_file():
            raise ValueError('Missing required source: ' + name)
    scope = json.loads((folder / 'source-scope.json').read_text())
    suffix = scope.get('case_suffix')
    if suffix not in ('witness_1', 'witness_2'):
        raise ValueError('Unknown controlled case')
    return {
        'format': 'c405647-1a-saved-analysis-v1',
        'case_id': 'training__C405647__NRS-484B-267-1a__motor_vehicle_driver__' + suffix,
        'selected': False, 'draft_only': True,
        'measurements': {'emergency_approach_clearance': {
            'method': 'approach_clearance_and_lamp_timing',
            'value': approach_clearance_and_lamp_timing(folder),
            'sources': {name: _sha(folder / name) for name in SOURCES}}},
        'physical_acceptance_claimed': False, 'legal_verdict_claimed': False
    }


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    path = Path(args.output)
    if path.exists():
        raise ValueError('Analysis output already exists')
    path.write_text(json.dumps(analysis_report(args.attempt), indent=2) + '\n')
