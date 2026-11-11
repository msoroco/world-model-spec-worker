"""Test turn completion against original shaped sources; fixtures are synthetic."""

import argparse
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(case_id, kind):
    entries = json.loads((HERE / 'execution-manifest.json').read_text())['cases']
    entry = next((item for item in entries if item['case_id'] == case_id), None)
    if entry is None or kind not in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        raise ValueError('Unknown exact turn case or outcome')
    recipe = json.loads((ROOT / entry['fixture_recipe']).read_text())
    originals = json.loads((ROOT / recipe['generator']['source']).read_text())['files']
    with TemporaryDirectory(prefix='turn-motion-', dir=ROOT / '.runtime-work') as temp:
        base = Path(temp)
        names = ('ego_turn_motion.jsonl', 'affected_participants.json',
                 'participant_bodies.jsonl', 'video_frames.jsonl')
        for name in names:
            (base / name).write_text(originals[name])
        motion = base / 'ego_turn_motion.jsonl'
        if kind == 'missing_evidence':
            motion.unlink()
        elif kind == 'incomplete_motion':
            rows = [json.loads(line) for line in motion.read_text().splitlines()]
            for row in rows:
                row['ego_yaw_deg'] = rows[0]['ego_yaw_deg']
                row['y_m'] = rows[0]['y_m']
            motion.write_text(''.join(json.dumps(row) + '\n' for row in rows))
        sources = {name: _sha(base / name) for name in names if (base / name).is_file()}
        if not motion.is_file():
            status = 'unverified'
            observables = {}
        else:
            rows = [json.loads(line) for line in motion.read_text().splitlines()]
            frames = [row['frame'] for row in rows]
            video = [json.loads(line)['native_frame'] for line in
                     (base / 'video_frames.jsonl').read_text().splitlines()]
            bodies = [json.loads(line)['frame'] for line in
                      (base / 'participant_bodies.jsonl').read_text().splitlines()]
            if len(rows) < 2 or frames != sorted(set(frames)) or frames != video or frames != bodies:
                raise ValueError('Original turn frames do not join')
            yaw_change = abs(rows[-1]['ego_yaw_deg'] - rows[0]['ego_yaw_deg'])
            lateral = abs(rows[-1]['y_m'] - rows[0]['y_m'])
            status = 'met' if yaw_change > 45 and lateral > 2 else 'not_met'
            observables = {'first_frame': frames[0], 'last_frame': frames[-1],
                           'yaw_change_deg': yaw_change, 'lateral_displacement_m': lateral}
        expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                    'missing_evidence': 'unverified'}[kind]
        if status != expected:
            raise ValueError('Turn fixture did not yield expected outcome')
        return {'case_id': case_id, 'fixture_kind': kind, 'diagnostic_fixture': True,
                'actual_native_capture': False, 'provenance_kind': 'native',
                'provenance_note': 'Native-shaped synthetic source protocol only',
                'physical_checks': {'maneuver': {'status': status,
                    'method': 'joined original 20 Hz ego yaw and lateral travel across participant and video frames; engineering fixture criterion only',
                    'sources': sources,
                    'missing_evidence': ['ego_turn_motion.jsonl'] if kind == 'missing_evidence' else []}},
                'maneuver_completed': status == 'met', 'realized_observables': observables,
                'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--kind', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = run(args.case, args.kind)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(args.case, args.kind, result['physical_checks']['maneuver']['status'], 'synthetic_fixture_only')
