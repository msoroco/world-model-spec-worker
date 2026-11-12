"""Source-shaped turn completion protocol for the four exact cases."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(data):
    return hashlib.sha256(data.encode()).hexdigest()


def records(text):
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def run(case, kind):
    entries = json.loads((HERE / 'execution-manifest.json').read_text())['cases']
    entry = next((item for item in entries if item['case_id'] == case), None)
    if entry is None or kind not in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        raise ValueError('Unknown exact turn case or physical outcome')
    recipe = json.loads((ROOT / entry['fixture_recipe']).read_text())
    original = json.loads((ROOT / recipe['generator']['source']).read_text())['files']
    names = ('ego_turn_motion.jsonl', 'affected_participants.json',
             'participant_bodies.jsonl', 'video_frames.jsonl')
    if any(name not in original for name in names):
        raise ValueError('Missing original-shaped turn source')
    sources = {name: sha(original[name]) for name in names}
    if kind == 'missing_evidence':
        sources.pop('ego_turn_motion.jsonl')
        status, observables = 'unverified', {}
    else:
        motion = records(original['ego_turn_motion.jsonl'])
        frame_map = records(original['video_frames.jsonl'])
        bodies = records(original['participant_bodies.jsonl'])
        if kind == 'incomplete_motion':
            motion = [dict(row, ego_yaw_deg=motion[0]['ego_yaw_deg'],
                           y_m=motion[0]['y_m']) for row in motion]
            sources['ego_turn_motion.jsonl'] = sha(''.join(json.dumps(row) + '\n' for row in motion))
        frames = [row['frame'] for row in motion]
        if (len(frames) < 2 or frames != sorted(set(frames))
                or frames != [row['native_frame'] for row in frame_map]
                or frames != [row['frame'] for row in bodies]):
            raise ValueError('Original turn frame join differs')
        yaw = abs(motion[-1]['ego_yaw_deg'] - motion[0]['ego_yaw_deg'])
        lateral = abs(motion[-1]['y_m'] - motion[0]['y_m'])
        status = 'met' if yaw > 45 and lateral > 2 else 'not_met'
        observables = {'first_frame': frames[0], 'last_frame': frames[-1],
                       'yaw_change_deg': yaw, 'lateral_displacement_m': lateral}
    expected = {'complete_motion': 'met', 'incomplete_motion': 'not_met',
                'missing_evidence': 'unverified'}[kind]
    if status != expected:
        raise ValueError('Fixture does not exercise expected physical outcome')
    return {'case_id': case, 'fixture_kind': kind, 'diagnostic_fixture': True,
            'actual_native_capture': False, 'provenance_kind': 'native',
            'physical_checks': {'maneuver': {'status': status,
                'method': 'joined original-shaped ego yaw and lateral travel; engineering fixture criterion only',
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
    print(args.case, args.kind, result['physical_checks']['maneuver']['status'],
          'synthetic_fixture_only')
