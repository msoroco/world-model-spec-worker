"""Materialize exact root construction from the selected source-deferred runner."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def build():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    first = plan['cases'][0]['case_id']
    name = first.removeprefix(AID + '__')
    selected = json.loads((HERE / ('construction-compatibility-' + name + '.json')).read_text())
    embedded = {item['path']: item['content'] for item in selected['files']}
    config = json.loads(embedded['config.json'])
    camera_specs = [([1920, 1080] if index == 0 else [1280, 720])
                    for index in range(4)]
    config['cameras'] = [{'name': camera, 'width': size[0], 'height': size[1],
                          'fov_deg': 75, 'pose_strategy': subject}
                         for camera, size, subject in zip(
                             ('overview', 'approach', 'reference_corner', 'driver_reference'),
                             camera_specs, (row['subject'] for row in plan['camera_plan']['coverage']))]
    config['assignment_id'] = AID
    config['frame_count'] = 900
    config['supported_case_ids'] = [item['case_id'] for item in plan['cases']]
    config['plan_sha256'] = sha(HERE / 'case-plan.json')
    write(HERE / 'config.json', config)
    (HERE / 'runner.py').write_text((HERE / 'source_deferred_runner.py').read_text())
    construction = {key: selected[key] for key in ('law_id', 'cell_id', 'actor', 'case_id',
                                                    'entrypoint', 'recording_description')}
    construction['measurement_plan'] = {'case_id': first, 'procedure': 'delivery_audit.py',
                                        'original_frames': 900, 'legal_judgment': 'unresolved',
                                        'source_packets': ['reviewed_original_site', 'original_native_capture',
                                                           'four_camera_pixels', 'civil_clock_and_regulation']}
    construction['mechanisms'] = ['source-gated passenger-zone construction',
                                  'same-tick PipelineCapture and four original cameras',
                                  '900-frame passenger event and civil-time measurement']
    construction['static_checks'] = ['exact law/cell/case identity',
                                      'reviewed source provenance and site hash',
                                      'four-camera 20 Hz original frame joins']
    construction['termination_rules'] = ['900 original ticks at 20 Hz',
                                         'fail closed on missing original site or Native observation']
    paths = ('runner.py', 'original_runner.py', 'passenger_zone.py', 'config.json',
             'tests/test_bundle.py', 'scene.json')
    (HERE / 'scene.json').write_text(embedded['scene.json'])
    (HERE / 'tests/test_bundle.py').write_text(embedded['tests/test_bundle.py'])
    construction['files'] = [{'path': path, 'content': (HERE / path).read_text()} for path in paths]
    write(HERE / 'construction.json', construction)


if __name__ == '__main__':
    build()
