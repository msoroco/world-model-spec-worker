"""Bind the existing witness_1 Native construction to a current v2 CPU draft."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NATIVE = HERE / 'native'
OUT = HERE / 'v2-primary/witness_1'
CASE = HERE.name + '__witness_1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    draft = json.loads((NATIVE / 'runtime-drafts/witness_1/primary/construction.json').read_text())
    bundle = NATIVE / 'drafts/witness_1/primary'
    construction = dict(draft)
    construction['files'] = [dict(item) for item in draft['files']]
    for item in construction['files']:
        if item['path'] == 'work/' + HERE.name + '/native/capture.py':
            item['content'] = (NATIVE / 'capture.py').read_text()
    construction['files'].append({'path': 'work/' + HERE.name + '/native/signal_heads.py',
        'content': (NATIVE / 'signal_heads.py').read_text()})
    construction['files'].append({'path': 'tests/test_signal_heads.py',
        'content': '''import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "work" / "ASSIGNMENT" / "native"))
from signal_heads import resolve, sample

class Actor:
    type_id = "traffic.traffic_light"
    def __init__(self, actor_id, source_id, state):
        self.id, self.source_id, self.state = actor_id, source_id, state
    def get_opendrive_id(self):
        return self.source_id
    def get_state(self):
        return self.state

class SignalIdentity(unittest.TestCase):
    def test_distinct_authored_heads(self):
        red = Actor(1, "601", "Red")
        arrow = Actor(2, "1603", "Green")
        self.assertEqual(sample(*resolve([arrow, red]))["arrow"]["opendrive_id"], "1603")
        with self.assertRaises(ValueError):
            resolve([red])
        with self.assertRaises(ValueError):
            resolve([red, red, arrow])
        with self.assertRaises(ValueError):
            sample(red, Actor(2, "1603", "Yellow"))
'''.replace('ASSIGNMENT', HERE.name)})
    construction['files'].append({'path': 'road.xodr',
        'content': (bundle / 'arrow-intersection.xodr').read_text()})
    recording = {'channels': [{'name': 'native_actor_signal_samples',
        'unit': 'structured', 'sampling_rate_hz': 20,
        'method': 'original Native actor and OpenDRIVE signal-head readback',
        'time_window': 'full 30 s / 600-frame attempt',
        'reference_frame': 'Native actor, map and camera-frame identities',
        'uncertainty': 'Directional-arrow pixels, governance and lawful use require independent review'}],
        'context_inputs': [], 'limitations': ['CPU source-shape draft has no physical Native pixels or legal verdict']}
    config = {'case_id': CASE, 'selected_case_id': CASE,
        'case': {'case_id': CASE}, 'cell_id': 'C111603',
        'law_id': 'NRS-484B-307-9a', 'actor': 'motor_vehicle_driver',
        'duration_s': 30, 'rate_hz': 20,
        'cameras': [{'name': name, 'width': width, 'height': height}
            for name, width, height in (('overview', 1920, 1080),
              ('approach', 1280, 720), ('reference_corner', 1280, 720),
              ('driver_reference', 1280, 720))],
        'required_atoms': ['ru.motor_vehicle', 'kin.position', 'kin.heading'],
        'source_packets': [], 'recording_description': recording}
    construction['files'].append({'path': 'config.json',
                                  'content': json.dumps(config, indent=2) + '\n'})
    construction['recording_description'] = recording
    construction['status'] = 'unselected_current_v2_cpu_diagnostic'
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / 'construction.json'
    path.write_text(json.dumps(construction, indent=2) + '\n')
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': HERE.name,
        'runtime_manifest_sha256': sha(ROOT / 'runtime/pipeline/SOURCE-MANIFEST.json'),
        'status': 'unselected_current_v2_cpu_primary_draft',
        'cases': [{'case_id': CASE, 'kind': 'unselected_cpu_diagnostic',
                   'construction': str(path.relative_to(HERE)),
                   'construction_sha256': sha(path), 'candidates': []}]}
    manifest_path = HERE / 'v2-primary-manifest.json'
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'manifest_sha256': sha(manifest_path),
                      'construction_sha256': sha(path),
                      'files': len(construction['files'])}))


if __name__ == '__main__':
    main()
