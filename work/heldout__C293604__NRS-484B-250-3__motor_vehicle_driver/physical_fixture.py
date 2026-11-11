"""Synthetic Native-shaped physical protocol for two opposing-left cases."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from opposing_left_measurement import measure_opposing_left

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def run(case_id, kind):
    entry = next((e for e in json.loads((HERE / 'execution-manifest.json').read_text())['cases']
                  if e['case_id'] == case_id), None)
    if entry is None or kind not in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        raise ValueError('Unknown exact case or physical fixture kind')
    intent_hold = (case_id.endswith('__opposing_left_intent_hold') or
                   case_id.endswith('__turn_release_delay-0001'))
    recipe = json.loads((ROOT / entry['fixture_recipe']).read_text())
    diagnostic = json.loads((ROOT / recipe['generator']['source']).read_text())['files']
    with TemporaryDirectory(prefix='opposing-left-physical-', dir=ROOT / '.runtime-work') as temp:
        base = Path(temp)
        names = ('opposing_left_context.json', 'opposing_left_participants.jsonl',
                 'trace.jsonl', 'video_frames.jsonl')
        if 'turn_heading_last_rad.jsonl' in diagnostic:
            names += ('turn_heading_last_rad.jsonl',)
        for name in names:
            (base / name).write_text(diagnostic[name])
        participants = base / 'opposing_left_participants.jsonl'
        if kind == 'missing_evidence':
            participants.unlink()
        elif kind == 'incomplete_motion':
            rows = [json.loads(line) for line in participants.read_text().splitlines()]
            rows[-1]['turning_heading_rad'] = 1.57 if intent_hold else 0.0
            rows[-1]['value']['turning_heading_rad'] = rows[-1]['turning_heading_rad']
            participants.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            if 'turn_heading_last_rad.jsonl' in diagnostic:
                headings = [json.loads(line) for line in
                            (base / 'turn_heading_last_rad.jsonl').read_text().splitlines()]
                headings[-1]['value'] = rows[-1]['turning_heading_rad']
                (base / 'turn_heading_last_rad.jsonl').write_text(
                    ''.join(json.dumps(row) + '\n' for row in headings))
        sources = {name: digest(base / name) for name in names if (base / name).is_file()}
        observation = None
        if kind == 'missing_evidence':
            try:
                measure_opposing_left(base)
            except ValueError as error:
                if 'Missing required source: opposing_left_participants.jsonl' not in str(error):
                    raise
            else:
                raise ValueError('Missing original participant source was accepted')
            status = 'unverified'
        else:
            observation = measure_opposing_left(base)['value']
            change = abs(observation['observed_turn_heading_change_rad'])
            # Engineering fixture discriminator only; it is not a legal cutoff.
            met = change < .05 if intent_hold else change > .5
            status = 'met' if met else 'not_met'
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if status != expected:
            raise ValueError('Opposing-left physical fixture status differs')
        method = ('original 20 Hz body and heading readback for planned left-turn hold'
                  if intent_hold else 'original 20 Hz body and heading readback for leftward motion')
        return {'case_id': case_id, 'fixture_kind': kind, 'fixture_only': True,
                'diagnostic_fixture': True, 'actual_native_capture': False,
                'physical_checks': {'maneuver': {'status': status, 'method': method,
                    'sources': sources,
                    'missing_evidence': ['opposing_left_participants.jsonl']
                    if kind == 'missing_evidence' else []}},
                'maneuver_completed': status == 'met',
                'realized_observables': {'observed_turn_heading_change_rad':
                    observation['observed_turn_heading_change_rad']} if observation else {},
                'provenance_kind': 'native',
                'provenance_note': 'Native-shaped synthetic protocol only; hold completion is not turn completion',
                'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


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
