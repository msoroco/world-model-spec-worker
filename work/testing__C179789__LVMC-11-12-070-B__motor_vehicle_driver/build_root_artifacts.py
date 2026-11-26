"""Materialize the canonical source-gated two-actor root bundle."""
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
    selected = json.loads((HERE / ('construction-' + name + '.json')).read_text())
    embedded = {item['path']: item['content'] for item in selected['files']}
    config = json.loads(embedded['config.json'])
    sizes = [(1920, 1080), (1280, 720), (1280, 720), (1280, 720)]
    config['cameras'] = [{'name': camera, 'width': size[0], 'height': size[1],
                          'fov_deg': 75, 'pose_strategy': subject}
                         for camera, size, subject in zip(
                             ('overview', 'approach', 'reference_corner', 'driver_reference'),
                             sizes, (row['subject'] for row in plan['camera_plan']['coverage']))]
    config['frame_count'] = 900
    config['supported_case_ids'] = [item['case_id'] for item in plan['cases']]
    config['plan_sha256'] = sha(HERE / 'case-plan.json')
    write(HERE / 'config.json', config)
    (HERE / 'runner.py').write_text((HERE / 'source_deferred_runner.py').read_text())
    (HERE / 'scene.json').write_text(embedded['scene.json'])
    (HERE / 'tests/test_bundle.py').write_text(
        '"""Root exact source-deferred bundle preflight."""\n'
        'import sys\nfrom pathlib import Path\n'
        'sys.path.insert(0, str(Path(__file__).resolve().parents[1]))\n'
        'from runner import check\n\n'
        'def test_bundle():\n'
        '    case_id, name = check()\n'
        '    assert case_id.endswith("__" + name)\n')
    construction = {key: selected[key] for key in ('law_id', 'cell_id', 'actor', 'case_id',
                                                    'entrypoint', 'recording_description')}
    construction['measurement_plan'] = {'case_id': first, 'procedure': 'delivery_audit.py',
                                        'original_frames': 900, 'legal_judgment': 'unresolved',
                                        'source_packets': ['reviewed_original_site', 'original_native_capture',
                                                           'four_camera_pixels', 'antecedent_review']}
    construction['mechanisms'] = ['reviewed through-highway two-actor source gate',
                                  'same-tick PipelineCapture and four original cameras',
                                  '900-frame conflict and antecedent observation']
    construction['static_checks'] = ['exact law/cell/case identity',
                                     'reviewed source and map hash',
                                     'four-camera 20 Hz original frame joins']
    construction['termination_rules'] = ['900 original ticks at 20 Hz',
                                        'fail closed on missing original site or Native observation']
    paths = ('runner.py', 'original_runner.py', 'through_highway.py', 'config.json',
             'tests/test_bundle.py', 'scene.json')
    construction['files'] = [{'path': path, 'content': (HERE / path).read_text()} for path in paths]
    write(HERE / 'construction.json', construction)


if __name__ == '__main__':
    build()
