"""Build three exact left turns with three bounded physical-risk alternatives."""

from hashlib import sha256
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CASES = ('centerline_approach_left_curb_departure',
         'farther_approach_left_curb_departure',
         'centerline_approach_farther_departure')


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def main():
    # This survey is explicitly diagnostic. A physical Native map/authority
    # survey must replace it before a capture can establish this intersection.
    survey = {'format': 'diagnostic-turn-route-survey', 'provenance_kind': 'synthetic_fixture',
        'map_name': 'diagnostic-map', 'approach_directions': 2,
        'destination_directions': 1, 'intersection_kind': 'public_highway_non_alley',
        'waypoints': [{'road_id': road, 'lane_id': lane, 's': s, 'xy_m': xy}
                      for road, lane, s, xy in [(1, -1, 0, [0,-8]),
                                                (1, -1, 5, [0,-3]),
                                                (2, -1, 1, [-2,0]),
                                                (2, -1, 5, [-6,0])]],
        'approach_centerline_xy_m': [[0,-10],[0,0]],
        'destination_left_curb_xy_m': [[0,-3],[-10,-3]],
        'intersection_entry_xy_m': [0,0],
        'note': 'Synthetic CPU survey, not a verified Native highway or legal authority.'}
    survey_text = json.dumps(survey, indent=2) + '\n'
    (ROOT / 'turn-route-survey.json').write_text(survey_text)
    source_hash = sha256(survey_text.encode()).hexdigest()
    description = {'channels': [{'name': 'turn_centerline_offset', 'unit': 'm',
        'method': 'original full-body corners relative to directed approach centerline',
        'sampling_rate_hz': 20, 'time_window': 'all original frames',
        'reference_frame': 'Native map ground plane',
        'uncertainty': 'Native bounding-box and surveyed line precision'}],
        'context_inputs': [],
        'limitations': ['No numerical nearest/practicable legal cutoff is supplied.']}
    code = ['turn_native.py', 'turn_camera.py', 'turn_geometry.py',
            'turn_source_measurement.py', 'turn_finalizer.py']
    tests = sorted((ROOT / 'tests').glob('test*.py'))
    entries = []
    for suffix in CASES:
        case = ROOT.name + '__' + suffix
        base = {'selected_case_id': case, 'law_id': 'NRS-484B-400-3',
            'cell_id': 'C109705', 'actor': 'motor_vehicle_driver',
            'rate_hz': 20, 'frames': 160, 'duration_s': 8,
            'required_atoms': [], 'source_packets': [],
            'cameras': ['overview','approach','reference_corner','driver_reference'],
            'target_speed_mps': 3.0, 'lookahead_steps': 2,
            'overview_height_delta_m': 0,
            'route_survey': {**survey, 'source_sha256': source_hash},
            'case': {'recording_description': description}}
        variants = [('primary', {}), ('fallback1', {'lookahead_steps': 1}),
                    ('fallback2', {'target_speed_mps': 2.0}),
                    ('fallback3', {'overview_height_delta_m': 2})]
        candidates = []
        for candidate, changes in variants:
            config = {**base, **changes}
            files = [{'path': 'config.json', 'content': json.dumps(config, indent=2)+'\n'},
                     {'path': 'turn-route-survey.json', 'content': survey_text}]
            files += [{'path': name, 'content': (ROOT / name).read_text()} for name in code]
            files += [{'path': 'tests/' + path.name, 'content': path.read_text()} for path in tests]
            construction = {'format': 'worker-inline-construction',
                'case_id': case, 'law_id': base['law_id'], 'cell_id': base['cell_id'],
                'actor': base['actor'], 'entrypoint': 'turn_native.py',
                'recording_description': description, 'files': files,
                'measurement_plan': {'original_rows': 'turn_road_geometry.json, body_footprints.jsonl and video_frames.jsonl',
                                     'saved_finalizer': 'turn_finalizer.py',
                                     'legal_judgment': None},
                'termination_rules': ['160 original frames at 20 Hz'],
                'mechanisms': ['sourced Native XODR turn route',
                               'full-body original frame capture',
                               'four synchronized RGB source cameras']}
            path = ROOT / 'cases' / f'construction-{suffix}-{candidate}.json'
            path.parent.mkdir(exist_ok=True)
            path.write_text(json.dumps(construction, indent=2)+'\n')
            reference = {'id': candidate, 'construction': str(path.relative_to(ROOT)),
                         'construction_sha256': digest(path)}
            if candidate == 'primary':
                entry = {'case_id': case, **{key: reference[key] for key in ('construction','construction_sha256')},
                         'candidate_risk': {'status': 'physical',
                         'reason': 'Turn route tracking and participant camera coverage may fail on the Native map.'},
                         'candidates': candidates}
            else:
                trigger = {'fallback1': ('original motion','turn route tracking','body leaves surveyed turn corridor'),
                           'fallback2': ('original motion','turn overshoot','vehicle crosses destination curb'),
                           'fallback3': ('four original cameras','turn body visibility','body obscured in overview')}[candidate]
                reference.update({'trigger': dict(zip(('source','metric','failure_condition'), trigger)),
                                  'changed_knobs': list(changes)})
                candidates.append(reference)
        entries.append(entry)
    manifest = {'format': 'worker-construction-probe-manifest',
                'assignment_id': ROOT.name, 'cases': entries}
    (ROOT / 'construction-probe-manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    print('Three exact turn constructions and nine alternatives built')


if __name__ == '__main__':main()
