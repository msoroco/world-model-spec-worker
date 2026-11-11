"""Replay source-bound categorical comparison points from returned work files.

The four positive sources are diagnostic Native-shaped fixtures. Counterfactual
points are rejected by the same source readers used for selected cases.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
LINKED = HERE.parent / 'heldout__C293604__NRS-484B-250-3__motor_vehicle_driver'
sys.path.insert(0, str(LINKED))
from opposing_left_comparison_audit import audit as audit_left
from opposing_left_measurement import measure_opposing_left
from ending_road_measurement import classify_approaches, measure
from official_control_comparison_audit import audit_sources


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def source(spec, key):
    item = spec['positive_points'][key]
    path = ROOT / item['diagnostic']
    if not path.is_file() or digest(path) != item['sha256']:
        raise ValueError('Returned diagnostic source hash differs: ' + key)
    raw = json.loads(path.read_text())
    if not isinstance(raw.get('files'), dict):
        raise ValueError('Diagnostic lacks original source files: ' + key)
    return raw['files'], item


def reject(action, expected):
    try:
        action()
    except ValueError as error:
        if expected not in str(error):
            raise
        return str(error)
    raise ValueError('Counterfactual source was accepted: ' + expected)


def write_left(directory, files, case_id):
    directory.mkdir()
    for name in ('opposing_left_context.json', 'opposing_left_participants.jsonl',
                 'video_frames.jsonl', 'trace.jsonl'):
        if name not in files:
            raise ValueError('Missing returned opposing-left source: ' + name)
        (directory / name).write_text(files[name])
    (directory / 'config.json').write_text(json.dumps({'selected_case_id': case_id}) + '\n')


def audit(spec):
    if spec.get('format') != 'worker-portable-categorical-comparison-points':
        raise ValueError('Wrong portable comparison point format')
    ending, ending_item = source(spec, 'ending_uncontrolled')
    official, official_item = source(spec, 'ending_governed')
    turning, turning_item = source(spec, 'opposing_left_turn')
    holding, holding_item = source(spec, 'opposing_left_hold')
    control = audit_sources(ending, official)
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        top = root / 'intersection_topology.json'
        bodies = root / 'intersection_participants.jsonl'
        top.write_text(ending['intersection_topology.json'])
        bodies.write_text(ending['intersection_participants.jsonl'])
        observation = measure(top, bodies)
        roles = observation['approaches']
        if roles['subject']['continues_beyond_junction'] or not roles['other']['continues_beyond_junction']:
            raise ValueError('Ending/through category missing from original diagnostic source')
        topology = json.loads(ending['intersection_topology.json'])
        altered = json.loads(json.dumps(topology))
        altered['lanes'][roles['subject']['exterior_lanes'][0]]['highway_id'] = roles['subject']['highway_id']
        bad_subject = reject(lambda: classify_approaches(altered), 'Subject highway does not end')
        altered = json.loads(json.dumps(topology))
        altered['lanes'][roles['other']['exterior_lanes'][0]]['highway_id'] = 'synthetic_other_highway'
        bad_other = reject(lambda: classify_approaches(altered), 'Other highway is not through')
        altered_control = dict(official)
        states = [json.loads(line) for line in official['official_device_states.jsonl'].splitlines()
                  if line.strip()]
        states[0]['device_id'] = 'tampered-device'
        altered_control['official_device_states.jsonl'] = ''.join(json.dumps(row) + '\n' for row in states)
        bad_device = reject(lambda: audit_sources(ending, altered_control),
                            'Official device state/frame join differs')
        turn_dir, hold_dir = root / 'turn', root / 'hold'
        write_left(turn_dir, turning, turning_item['case_id'])
        write_left(hold_dir, holding, holding_item['case_id'])
        left = audit_left(turn_dir, hold_dir)
        turn = measure_opposing_left(turn_dir)['value']
        hold = measure_opposing_left(hold_dir)['value']
        context_path = turn_dir / 'opposing_left_context.json'
        original = json.loads(context_path.read_text())
        altered = json.loads(json.dumps(original))
        altered['opposite_route'][0]['heading_xy'] = altered['turning_route'][0]['heading_xy']
        context_path.write_text(json.dumps(altered) + '\n')
        bad_same = reject(lambda: measure_opposing_left(turn_dir),
                          'does not establish opposing leftward plan')
        altered = json.loads(json.dumps(original))
        altered['turning_route'][-1]['heading_xy'] = altered['turning_route'][0]['heading_xy']
        context_path.write_text(json.dumps(altered) + '\n')
        bad_straight = reject(lambda: measure_opposing_left(turn_dir),
                              'does not establish opposing leftward plan')
        altered['opposite_route'][0]['heading_xy'] = altered['turning_route'][0]['heading_xy']
        context_path.write_text(json.dumps(altered) + '\n')
        bad_same_straight = reject(lambda: measure_opposing_left(turn_dir),
                                   'does not establish opposing leftward plan')
    return {'format': 'worker-portable-categorical-comparison-proof',
            'law_id': spec['law_id'],
            'source_diagnostics': {key: item['sha256'] for key, item in spec['positive_points'].items()},
            'positive_cases': {key: item['case_id'] for key, item in spec['positive_points'].items()},
            'ending_topology_sha256': sha256(ending['intersection_topology.json'].encode()).hexdigest(),
            'device_context_sha256': control['controlled_context_sha256'],
            'opposing_context_sha256': left['fixed_context_sha256'],
            'fixed_control_frame_sha256': control['fixed_originals']['video_frames.jsonl'],
            'ending_roles': roles, 'device_frames': control['device_frames'],
            'opposing_approach_heading_dot': turn['approach_heading_dot'],
            'planned_left_cross': turn['planned_left_cross'],
            'turn_heading_change_rad': turn['observed_turn_heading_change_rad'],
            'hold_heading_change_rad': hold['observed_turn_heading_change_rad'],
            'negative_rejections': [bad_subject, bad_other, bad_device,
                                    bad_same, bad_straight, bad_same_straight],
            'original_native_capture_claimed': False, 'legal_judgment_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--spec', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    spec_path = Path(args.spec)
    result = audit(json.loads(spec_path.read_text()))
    result['spec_sha256'] = digest(spec_path)
    result['script_sha256'] = digest(__file__)
    Path(args.output).write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'format': result['format'], 'negative_rejections':
                      len(result['negative_rejections'])}))


if __name__ == '__main__':
    main()
