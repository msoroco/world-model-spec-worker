"""Source-driven overtaking outcome protocol fixtures; no CARLA capture claim."""

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
os.environ.setdefault('SCENARIO_PIPELINE_OUTPUT_ROOT',
                      str(ROOT / '.runtime-work/c110161-pipeline-output'))
sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
from worker_exchange.fixture_recipe import materialize as make_fixture
from worker_exchange.runtime_cli import materialize as make_attempt
from worker_exchange.saved_processing import copy_sources
from overtake_measurement import measure


def run(case_id, kind):
    manifest = HERE / 'execution-manifest.json'
    entry = next((item for item in json.loads(manifest.read_text())['cases']
                  if item['case_id'] == case_id), None)
    if entry is None or kind not in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        raise ValueError('Unknown exact overtake case or fixture kind')
    with TemporaryDirectory(prefix='overtake-motion-', dir=ROOT / '.runtime-work') as temp:
        base = Path(temp)
        make_fixture(ROOT, ROOT / entry['fixture_recipe'], base / 'fixture')
        make_attempt(manifest, case_id, base / 'attempt')
        copy_sources(base / 'fixture', base / 'attempt')
        source = base / 'attempt/participant_footprints.jsonl'
        if kind == 'missing_evidence':
            source.unlink()
        elif kind == 'incomplete_motion':
            rows = [json.loads(line) for line in source.read_text().splitlines()]
            # Preserve frames and body lengths, but remove every lateral return.
            for row in rows:
                low = min(point[1] for point in row['ego_corners'])
                delta = 4.0 - low
                for point in row['ego_corners']:
                    point[1] += delta
            source.write_text(''.join(json.dumps(row, allow_nan=False) + '\n' for row in rows))
        sources = {name: sha256((base / 'attempt' / name).read_bytes()).hexdigest()
                   for name in ('trace.jsonl', 'video_frames.jsonl',
                                'participant_footprints.jsonl')
                   if (base / 'attempt' / name).is_file()}
        observation = None
        if kind == 'complete_motion':
            observation = measure(source)
            status = ('met' if observation['all_abreast_left']
                      and observation['first_return_frame'] > observation['abreast_frames'][0]
                      else 'not_met')
        else:
            try:
                measure(source)
            except ValueError as error:
                expected = ('Missing required source' if kind == 'missing_evidence'
                            else 'No measured rightward return')
                if expected not in str(error):
                    raise
            else:
                raise ValueError('Incomplete overtaking source was accepted')
            status = 'unverified' if kind == 'missing_evidence' else 'not_met'
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if status != expected:
            raise ValueError(f'Overtake physical fixture returned {status}, expected {expected}')
        return {'case_id': case_id, 'fixture_kind': kind, 'fixture_only': True,
                'diagnostic_fixture': True, 'actual_native_capture': False,
                'physical_checks': {'maneuver': {'status': status,
                    'method': 'original source body overlap, same-direction left pass, and first return',
                    'sources': sources,
                    'missing_evidence': ['participant_footprints.jsonl']
                                        if kind == 'missing_evidence' else []}},
                'maneuver_completed': status == 'met',
                'realized_observables': ({'abreast_frames': observation['abreast_frames'],
                                         'first_return_frame': observation['first_return_frame'],
                                         'minimum_gap_m': observation['min_abreast_lateral_gap_m']}
                                        if observation else {}),
                'provenance_kind': 'native',
                'provenance_note': 'Native-shaped synthetic source protocol test only',
                'physical_acceptance_claimed': False,
                'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', required=True,
                        choices=('complete_motion', 'incomplete_motion', 'missing_evidence'))
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = run(args.case, args.kind)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(args.case, args.kind, result['physical_checks']['maneuver']['status'],
          'synthetic_fixture_only')
