"""Build the first exact C10364 CPU-only diagnostic construction bundle."""

from hashlib import sha256
import json
from pathlib import Path


root = Path(__file__).resolve().parent
cases_dir = root / 'cases'
cases_dir.mkdir(exist_ok=True)
aid = root.name
case_id = aid + '__person_3mps'
semantic = json.loads((root / 'proposals/cases.json').read_text())
selected = next(case for case in semantic['cases'] if case['case_id'] == case_id)
polygon = {'format': 'diagnostic-alley-polygon',
           'provenance_kind': 'synthetic_fixture',
           'polygon_xy': [[0,-3],[40,-3],[40,3],[0,3]],
           'note': 'CPU route-selector fixture only; no selected Native alley geometry or physical exposure.'}
polygon_text = json.dumps(polygon, indent=2) + '\n'
polygon_path = cases_dir / 'diagnostic-alley-polygon.json'
polygon_path.write_text(polygon_text)
config = {'selected_case_id': case_id,
          'law_id': 'NRS-484B-600-1b', 'cell_id': 'C10364',
          'actor': 'motor_vehicle_driver',
          'rate_hz': 20, 'frames': 160, 'duration_s': 8,
          'target_speed_mps': 3.0, 'protected_interest': 'person',
          'pedestrian_offset_m': 1.8,
          'alley_direction': 'east', 'alley_width_m': 6.0,
          'alley_polygon_xy': polygon['polygon_xy'],
          'alley_polygon_source': {'path': 'diagnostic-alley-polygon.json',
                                   'sha256': sha256(polygon_text.encode()).hexdigest()},
          'construction_probe_only': True, 'required_atoms': [],
          'case': {'recording_description': selected['recording_description']}}
sources = ['native_alley_cases.py', 'alley_case_setup.py', 'alley_route.py',
           'alley_geometry.py', 'alley_camera.py', 'alley_source_capture.py',
           'alley_measurement.py', 'alley_finalizer.py',
           'alley_comparison_audit.py']
test_sources = sorted(path for path in (root / 'tests').glob('test*.py'))
files = [{'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'},
         {'path': 'diagnostic-alley-polygon.json', 'content': polygon_text}]
files += [{'path': name, 'content': (root / name).read_text()}
          for name in sources]
files += [{'path': 'tests/' + path.name, 'content': path.read_text()}
          for path in test_sources]
construction = {
    'format': 'worker-inline-construction',
    'case_id': case_id, 'cell_id': 'C10364',
    'law_id': 'NRS-484B-600-1b', 'actor': 'motor_vehicle_driver',
    'entrypoint': 'native_alley_cases.py',
    'recording_description': selected['recording_description'],
    'files': files,
    'measurement_plan': {'original_rows': 'participant_footprints.jsonl and ego_motion.jsonl',
                         'saved_finalizer': 'alley_finalizer.py',
                         'legal_judgment': None},
    'static_checks': ['six exact engineering settings and hashed polygon geometry',
                      'four named original cameras and synchronized source recorder'],
    'termination_rules': ['160 original frames at 20 Hz after materialized capture'],
    'mechanisms': ['connected polygon-bounded route',
                   'stationary pedestrian and owned property',
                   'feedback speed controller',
                   'original three-body footprint/motion sources',
                   'four synchronized RGB streams']}
path = cases_dir / 'construction-person_3mps.json'
path.write_text(json.dumps(construction, indent=2) + '\n')
manifest = {'format': 'worker-construction-probe-manifest',
            'assignment_id': aid,
            'cases': [{'case_id': case_id,
                       'construction': str(path.relative_to(root)),
                       'construction_sha256': sha256(path.read_bytes()).hexdigest()}]}
for planned in semantic['cases']:
    next_id = planned['case_id']
    if planned['target_type'] == 'baseline' or next_id == case_id:
        continue
    suffix = next_id[len(aid + '__'):]
    next_construction = json.loads(json.dumps(construction))
    next_construction['case_id'] = next_id
    next_construction['recording_description'] = planned['recording_description']
    next_config = json.loads(next_construction['files'][0]['content'])
    next_config['selected_case_id'] = next_id
    next_config['target_speed_mps'] = planned['variable_assignments']['target_speed_mps']['value']
    next_config['protected_interest'] = planned['variable_assignments']['protected_interest']['value']
    next_config['pedestrian_offset_m'] = planned['variable_assignments']['pedestrian_offset_m']['value']
    next_config['case']['recording_description'] = planned['recording_description']
    next_construction['files'][0]['content'] = json.dumps(next_config, indent=2) + '\n'
    next_path = cases_dir / ('construction-' + suffix + '.json')
    next_path.write_text(json.dumps(next_construction, indent=2) + '\n')
    manifest['cases'].append({'case_id': next_id,
        'construction': str(next_path.relative_to(root)),
        'construction_sha256': sha256(next_path.read_bytes()).hexdigest()})
(root / 'construction-probe-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print('Built ' + str(len(manifest['cases'])) + ' exact diagnostic alley constructions')
