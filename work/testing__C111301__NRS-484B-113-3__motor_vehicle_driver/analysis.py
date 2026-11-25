"""Recorded-only C111301 backing measurement; no legal priority verdict."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from saved_backing import process

SOURCES = ('acquisition.json', 'map.json', 'road.xodr',
           'telemetry.json', 'frame-map.json')


def _source_hashes(attempt):
    sources = {}
    for name in SOURCES:
        path = Path(attempt) / name
        if not path.is_file():
            raise ValueError('Missing required source: ' + name)
        sources[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return sources


def measure_pedestrian_precedence(measured):
    return {'response_witness': measured['response_witness'],
            'corridor_basis': measured['corridor_basis'],
            'moving_pedestrian_and_reverse_measured': True,
            'statutory_priority_verdict': None}


def analyze(attempt):
    attempt = Path(attempt).resolve()
    source_hashes = _source_hashes(attempt)
    config = json.loads((attempt / 'config.json').read_text())
    case_id = config.get('selected_case_id')
    measured = process(attempt, case_id)
    if any(hashlib.sha256((attempt / name).read_bytes()).hexdigest() != value
           for name, value in source_hashes.items()):
        raise ValueError('original backing source changed during analysis')
    return {'format': 'worker-analysis-report', 'case_id': case_id,
            'measurements': {'pedestrian_precedence': {
                'value': measure_pedestrian_precedence(measured),
                'method': 'measure_pedestrian_precedence',
                'sources': source_hashes}},
            'analysis_complete': True,
            'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False,
            'limitations': ['Measured response does not settle legal right of way.',
                            'Original video pixels and physical completion need independent review.']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = analyze(args.attempt)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
