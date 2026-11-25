"""Exercise measured completion states on explicitly synthetic Native-shaped traces."""
from __future__ import annotations
import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path[:0] = [str(REPO / 'runtime'), str(REPO / 'runtime/scenario_pipeline')]
from scenario_pipeline.worker_exchange.native_output import assess_physical


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + '\n')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(case, kind, scratch, result):
    if kind not in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        raise ValueError('unsupported synthetic physical outcome')
    manifest = json.loads((ROOT / 'execution-manifest.json').read_text())
    entry = next(x for x in manifest['cases'] if x['case_id'] == case)
    construction = json.loads((ROOT / entry['construction']).read_text())
    cfg = json.loads(next(x['content'] for x in construction['files'] if x['path'] == 'config.json'))
    scratch.mkdir(parents=True, exist_ok=False)
    write(scratch / 'config.json', cfg)
    with (scratch / 'video_frames.jsonl').open('w') as mapped:
        for i in range(900):
            mapped.write(json.dumps({'video_frame': i, 'carla_frame': i + 1,
                                     'native_frame': i + 1, 'time_s': i / 20}) + '\n')
    if kind != 'missing_evidence':
        total = 10.0 if kind == 'complete_motion' else 1.0
        with (scratch / 'trace.jsonl').open('w') as trace:
            for i in range(900):
                trace.write(json.dumps({'frame': i + 1, 'time_s': i / 20,
                                        'position_m': [total * i / 899, 0.0]}) + '\n')
    assessed = assess_physical(scratch, cfg, [])
    output = {'case_id': case, 'fixture_kind': kind, 'provenance_kind': 'synthetic_fixture',
              'diagnostic_fixture': True, 'construction_sha256': digest(ROOT / entry['construction']),
              'physical_checks': assessed['physical_checks'],
              'realized_observables': assessed['realized_observables'],
              'maneuver_completed': assessed['maneuver_completed'],
              'source_hashes': {p.name: digest(p) for p in scratch.iterdir() if p.is_file()},
              'legal_verdict_claimed': False, 'native_acceptance_claimed': False}
    write(result, output)
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[kind]
    actual = output['physical_checks']['maneuver']['status']
    if actual != expected:
        raise ValueError(f'physical fixture {kind} returned {actual}, expected {expected}')
    print(json.dumps({'case_id': case, 'fixture': kind, 'status': actual,
                      'source_hashes': output['source_hashes']}, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', required=True)
    parser.add_argument('--scratch', type=Path, required=True)
    parser.add_argument('--result', type=Path, required=True)
    args = parser.parse_args()
    run(args.case, args.kind, args.scratch, args.result)
