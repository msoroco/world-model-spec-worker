"""Build camera-framing and control-response alternatives for each exact case."""
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / 'execution-manifest.json'


def encode(value):
    return json.dumps(value, indent=2, sort_keys=True) + '\n'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def replace_once(source, old, new):
    if source.count(old) != 1:
        raise ValueError('Expected one fallback edit site: ' + old)
    return source.replace(old, new)


def add_candidate(entry, primary, number, source_name, edits, trigger, knobs, test):
    if any(c.get('id') == f'fallback{number}' for c in entry.get('candidates', [])):
        raise ValueError('Retain existing candidate and proof receipts')
    alternate = copy.deepcopy(primary)
    files = {f['path']: f for f in alternate['files']}
    for old, new in edits:
        files[source_name]['content'] = replace_once(files[source_name]['content'], old, new)
    files['tests/test_bundle.py']['content'] += '\n' + test + '\n'
    alternate['mechanisms'].append(knobs)
    side = entry['case_id'].rsplit('__', 1)[-1]
    path = ROOT / 'constructions' / f'{side}-fallback{number}.json'
    if path.exists():
        raise ValueError('Retain existing fallback file: ' + str(path))
    path.write_text(encode(alternate))
    candidate = {'id': f'fallback{number}', 'construction': str(path.relative_to(ROOT)),
                 'construction_sha256': sha(path), 'trigger': trigger,
                 'changed_knobs': [knobs]}
    entry['candidates'].append(candidate)
    return candidate


def build():
    manifest = json.loads(MANIFEST.read_text())
    made = []
    for entry in manifest['cases']:
        side = entry['case_id'].rsplit('__', 1)[-1]
        primary = json.loads((ROOT / entry['construction']).read_text())
        camera = add_candidate(
            entry, primary, 2, 'native_scene.py',
            [("(-18 * direction, -12, 24)", "(-10 * direction, -8, 16)"),
             ("(-42 * direction, -7, 8)", "(-30 * direction, -5, 10)")],
            {'source': 'original Native overview and approach video frames',
             'metric': 'officer arm pixel height during governing frames',
             'failure_condition': 'Visible arm below reviewable pixel size in primary framing'},
            'Move overview and approach camera poses closer to the officer and lower the overview height while retaining all four capture profiles',
            "from native_scene import camera_plan\n"
            "class CameraFallbackTest(unittest.TestCase):\n"
            "    def test_reframed_source_poses(self):\n"
            "        views=camera_plan(1)\n"
            "        self.assertEqual((-10,-8,16),views[0]['xyz'])\n"
            "        self.assertEqual((-30,-5,10),views[1]['xyz'])\n"
            "        self.assertEqual((1920,1080),views[0]['size'])\n")
        if side == 'reference':
            edits = [('braking_distance = speed_mps * speed_mps / 5.0 + 1.0',
                      'braking_distance = speed_mps * speed_mps / 3.0 + 2.0')]
            knobs = 'Increase reference braking distance by reducing the target deceleration from 2.5 to 1.5 m/s² and adding 2 m reserve'
            test = ("from officer_direction import Crossing,OfficerStop,target_control\n"
                    "class BrakeFallbackTest(unittest.TestCase):\n"
                    "    def test_earlier_braking_request(self):\n"
                    "        s=OfficerStop('206','205',1,0,1,600,'c177225_authored_rail_crossing',True)\n"
                    "        r=target_control(Crossing(),s,bus_id='205',crossing_id=s.crossing_id,direction=1,station_m=-40,speed_mps=10,frame=2,obey=True)\n"
                    "        self.assertEqual(1.0,r['brake'])\n")
            trigger = {'source': 'original Native bus velocity and station rows',
                       'metric': 'front-bumper distance to stop line at first zero-speed frame',
                       'failure_condition': 'Primary bus overshoots stop margin or cannot reach zero speed before the line'}
        else:
            edits = [("return {'throttle': 0.25, 'brake': 0.0, 'requested': 'continue_through_line'",
                      "return {'throttle': 0.18, 'brake': 0.0, 'requested': 'continue_through_line'")]
            knobs = 'Reduce contrast continue-through throttle request from 0.25 to 0.18 while retaining the explicit non-stop response'
            test = ("from officer_direction import Crossing,OfficerStop,target_control\n"
                    "class ThrottleFallbackTest(unittest.TestCase):\n"
                    "    def test_lower_continue_request(self):\n"
                    "        s=OfficerStop('206','205',1,0,1,600,'c177225_authored_rail_crossing',True)\n"
                    "        r=target_control(Crossing(),s,bus_id='205',crossing_id=s.crossing_id,direction=1,station_m=-40,speed_mps=5,frame=2,obey=False)\n"
                    "        self.assertEqual(0.18,r['throttle'])\n"
                    "        self.assertEqual('continue_through_line',r['requested'])\n")
            trigger = {'source': 'original Native bus trace and camera frame map',
                       'metric': 'bus lateral deviation and stable crossing-entry frame',
                       'failure_condition': 'Primary continuation destabilizes the bus before a visible crossing entry'}
        control = add_candidate(entry, primary, 3, 'officer_direction.py', edits, trigger, knobs, test)
        made.append({'case_id': entry['case_id'], 'fallback2_sha256': camera['construction_sha256'],
                     'fallback3_sha256': control['construction_sha256']})
    MANIFEST.write_text(encode(manifest))
    return made


if __name__ == '__main__':
    print(encode(build()))
