"""Build the current four-view Native entrypoint and root package from owned sources."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'offline/reference/primary'


def emit(path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


def build():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    old = json.loads((SOURCE / 'config.json').read_text())
    case_ids = [item['case_id'] for item in plan['cases']]
    names = ('overview', 'approach', 'reference_corner', 'driver_reference')
    sizes = ((1920, 1080), (1280, 720), (1280, 720), (1280, 720))
    fovs = (80, 80, old['policy']['camera_fov_deg'], 85)
    old.update(selected_case_id=case_ids[0], case={'case_id': case_ids[0]},
               required_atoms=[], source_packets=[], supported_case_ids=case_ids,
               cameras=[{'name': name, 'width': width, 'height': height,
                         'pose_strategy': 'authored Native sidewalk and heavy body coverage',
                         'fov_deg': fov}
                        for name, (width, height), fov in zip(names, sizes, fovs)])
    channels = [
        {'name': name, 'unit': unit, 'sampling_rate_hz': 20,
         'method': method, 'time_window': 'entire 30 second 600 frame attempt',
         'reference_frame': 'original Native frame and time',
         'uncertainty': '50 ms bracket; surveyed City authority and actual pixels unverified'}
        for name, unit, method in (
            ('ego_pose', 'm', 'Native actor position and full body corners'),
            ('ego_speed', 'm/s', 'Native actor velocity'),
            ('drive_within_sidewalk_area', 'bool', 'Full original body versus authored OpenDRIVE sidewalk proxy; City authority separately reviewed'),
            ('subject_pose_body_speed', 'structured', 'Native pose, body and velocity packet'),
            ('sidewalk_occupancy', 'structured', 'Source-bound spatial context measurement'))]
    recording = {'channels': channels,
                 'context_inputs': [],
                 'limitations': ['Original City authority, three-wheel exception facts, camera pixels, and legal judgment require local review']}
    old['recording_description'] = recording
    emit(HERE / 'config.json', old)
    sources = {'runner.py': HERE / 'native/runner.py',
               'road.xodr': HERE / 'native/road.xodr',
               'requested-tracks.jsonl': SOURCE / 'requested-tracks.jsonl',
               'assignment-source.json': HERE.parents[1] / 'inputs' / HERE.name / 'assignment.json',
               'case-plan.json': HERE / 'case-plan.json',
               'finalize.py': HERE / 'native/finalize_v2.py'}
    for name, source in sources.items():
        if source != HERE / name:
            (HERE / name).write_text(source.read_text())
    test = '''"""Source-bound root Native request checks."""
import json
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]


class NativeRequestTest(unittest.TestCase):
    def test_reference_native_request(self):
        process = subprocess.run([sys.executable, str(ROOT / 'runner.py'), '--check'],
                                 capture_output=True, text=True, check=True)
        result = json.loads(process.stdout)
        self.assertEqual(result['requested_frames'], 600)
        self.assertFalse(result['original_native_observed'])

    def test_current_four_view_profile(self):
        config = json.loads((ROOT / 'config.json').read_text())
        self.assertEqual([camera['name'] for camera in config['cameras']],
                         ['overview', 'approach', 'reference_corner', 'driver_reference'])
        self.assertEqual(config['duration_s'], 30)
'''
    (HERE / 'tests').mkdir(exist_ok=True)
    (HERE / 'tests/test_root.py').write_text(test)
    files = [{'path': name, 'content': (HERE / name).read_text()}
             for name in (*sources, 'config.json', 'tests/test_root.py')]
    construction = {'case_id': case_ids[0], 'cell_id': plan['cell_id'],
                    'law_id': plan['law_id'], 'actor': plan['actor'],
                    'entrypoint': 'runner.py', 'files': files,
                    'recording_description': recording,
                    'measurement_plan': ['source-bound full-body sidewalk overlap',
                                         'Native speed and frame join',
                                         'surveyed City sidewalk and entrance review'],
                    'static_checks': ['600 frame request', 'four-camera profile',
                                      'exact input and road hashes'],
                    'termination_rules': ['600 Native frames',
                                          'retain encoder and world restoration failure evidence'],
                    'mechanisms': ['authored two-way road with sidewalk lane',
                                   'heavy-vehicle Native steering and capture',
                                   'source-bound post-capture context qualification'],
                    'status': 'partial_native_package'}
    emit(HERE / 'construction.json', construction)
    return hashlib.sha256((HERE / 'construction.json').read_bytes()).hexdigest()


if __name__ == '__main__':
    print(build())
