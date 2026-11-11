"""Source-bound audit of categorical NRS-484B-250-3 alternatives.

Uses already selected exact constructions. It makes no legal or physical claim.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

HERE = Path(__file__).resolve().parent
LINKED = HERE.parent / 'heldout__C293604__NRS-484B-250-3__motor_vehicle_driver'
sys.path.insert(0, str(LINKED))
from opposing_left_comparison_audit import audit as audit_left
from opposing_left_measurement import measure_opposing_left
from ending_road_measurement import classify_approaches, measure
from official_control_comparison_audit import audit_sources


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def expect_rejection(action, text):
    try:
        action()
    except ValueError as error:
        if text not in str(error):
            raise
        return str(error)
    raise ValueError('Tampered categorical source was accepted: ' + text)


def audit(ending, official, turning, holding):
    ending, official, turning, holding = map(Path, (ending, official, turning, holding))
    for folder in (ending, official, turning, holding):
        if not folder.is_dir():
            raise ValueError('Missing selected source attempt: ' + str(folder))
    source_names = ('intersection_participants.jsonl', 'video_frames.jsonl',
                    'trace.jsonl', 'intersection_topology.json',
                    'control_inventory.json', 'official_device_context.json',
                    'official_device_states.jsonl')
    uncontrolled = {name: (ending / name).read_text() for name in source_names
                    if (ending / name).is_file()}
    controlled = {name: (official / name).read_text() for name in source_names
                  if (official / name).is_file()}
    ending_measure = measure(ending / 'intersection_topology.json',
                             ending / 'intersection_participants.jsonl')
    device_measure = measure(official / 'intersection_topology.json',
                             official / 'intersection_participants.jsonl')
    if ending_measure['approaches'] != device_measure['approaches']:
        raise ValueError('Highway roles changed across official-control pair')
    roles = ending_measure['approaches']
    if roles['subject']['continues_beyond_junction'] or not roles['other']['continues_beyond_junction']:
        raise ValueError('Ending/through Native highway categories missing')
    control = audit_sources(uncontrolled, controlled)
    topology = json.loads(uncontrolled['intersection_topology.json'])
    subject_exit = roles['subject']['exterior_lanes'][0]
    changed = json.loads(json.dumps(topology))
    changed['lanes'][subject_exit]['highway_id'] = roles['subject']['highway_id']
    bad_ending = expect_rejection(lambda: classify_approaches(changed),
                                  'Subject highway does not end')
    other_exit = roles['other']['exterior_lanes'][0]
    changed = json.loads(json.dumps(topology))
    changed['lanes'][other_exit]['highway_id'] = 'synthetic_other_highway'
    bad_through = expect_rejection(lambda: classify_approaches(changed),
                                   'Other highway is not through')
    changed_controlled = dict(controlled)
    states = [json.loads(line) for line in controlled['official_device_states.jsonl'].splitlines()
              if line.strip()]
    states[0]['device_id'] = 'tampered-device'
    changed_controlled['official_device_states.jsonl'] = ''.join(
        json.dumps(row) + '\n' for row in states)
    bad_device = expect_rejection(lambda: audit_sources(uncontrolled, changed_controlled),
                                  'Official device state/frame join differs')
    left = audit_left(turning, holding)
    turn = measure_opposing_left(turning)['value']
    hold = measure_opposing_left(holding)['value']
    with TemporaryDirectory() as temporary:
        temp = Path(temporary)
        for name in ('opposing_left_context.json', 'opposing_left_participants.jsonl',
                     'video_frames.jsonl'):
            (temp / name).write_bytes((turning / name).read_bytes())
        original_context = json.loads((temp / 'opposing_left_context.json').read_text())
        context = json.loads(json.dumps(original_context))
        context['opposite_route'][0]['heading_xy'] = context['turning_route'][0]['heading_xy']
        (temp / 'opposing_left_context.json').write_text(json.dumps(context) + '\n')
        bad_opposite = expect_rejection(lambda: measure_opposing_left(temp),
                                        'does not establish opposing leftward plan')
        context = json.loads(json.dumps(original_context))
        context['turning_route'][-1]['heading_xy'] = context['turning_route'][0]['heading_xy']
        (temp / 'opposing_left_context.json').write_text(json.dumps(context) + '\n')
        bad_straight = expect_rejection(lambda: measure_opposing_left(temp),
                                        'does not establish opposing leftward plan')
        context['opposite_route'][0]['heading_xy'] = context['turning_route'][0]['heading_xy']
        (temp / 'opposing_left_context.json').write_text(json.dumps(context) + '\n')
        bad_same_straight = expect_rejection(lambda: measure_opposing_left(temp),
                                             'does not establish opposing leftward plan')
    return {'format': 'worker-categorical-qualitative-source-matrix',
            'law_id': 'NRS-484B-250-3',
            'ending_case': json.loads((ending / 'config.json').read_text())['selected_case_id'],
            'official_case': json.loads((official / 'config.json').read_text())['selected_case_id'],
            'turn_case': left['turn_case'], 'hold_case': left['hold_case'],
            'ending_topology_sha256': digest(ending / 'intersection_topology.json'),
            'official_context_sha256': digest(official / 'official_device_context.json'),
            'turn_context_sha256': digest(turning / 'opposing_left_context.json'),
            'fixed_control_frame_sha256': control['fixed_originals']['video_frames.jsonl'],
            'source_roles': roles, 'device_frames': control['device_frames'],
            'opposing_approach_heading_dot': turn['approach_heading_dot'],
            'planned_left_cross': turn['planned_left_cross'],
            'observed_turn_heading_change_rad': turn['observed_turn_heading_change_rad'],
            'observed_hold_heading_change_rad': hold['observed_turn_heading_change_rad'],
            'negative_rejections': [bad_ending, bad_through, bad_device,
                                    bad_opposite, bad_straight, bad_same_straight],
            'native_capture_claimed': False, 'legal_judgment_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    for name in ('ending', 'official', 'turning', 'holding', 'output'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    result = audit(args.ending, args.official, args.turning, args.holding)
    path = Path(args.output)
    path.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'format': result['format'], 'negative_rejections':
                      len(result['negative_rejections'])}))


if __name__ == '__main__':
    main()
