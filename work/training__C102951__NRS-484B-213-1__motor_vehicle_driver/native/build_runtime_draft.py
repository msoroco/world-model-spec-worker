"""Pin all three distance requests and their fallbacks to runtime offline checks."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
DISTANCES = (70, 120, 170)
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')
FILES = ('config.json', 'requested-tracks.jsonl', 'road.xodr',
         'assignment-source.json', 'case-plan.json', 'runner.py',
         'measure_pass.py', 'measure_response.py', 'prepare_pass.py',
         'triggers.py', 'measurement-contract.json')
TEST = '''import json
import shutil
import tempfile
import unittest
from pathlib import Path
from runner import check, lookahead_index

CONFIG = json.loads(Path('config.json').read_text())
DISTANCE = CONFIG['distance_m']
CANDIDATE = CONFIG['candidate_id']

class ExactPassingRequest(unittest.TestCase):
    def test_600_frame_primary_and_four_cameras(self):
        result = check(Path.cwd(), DISTANCE, CANDIDATE)
        self.assertEqual(result['requested_frames'], 600)
        self.assertFalse(result['original_native_observed'])

    def test_last_controller_lookahead(self):
        self.assertEqual(lookahead_index(480,600),495)
        self.assertEqual(lookahead_index(599,600),599)

    def test_changed_source_rejected(self):
        with tempfile.TemporaryDirectory() as name:
            target = Path(name)
            for source in Path.cwd().iterdir():
                if source.is_file(): shutil.copy2(source,target/source.name)
            path = target/'config.json'
            data = json.loads(path.read_text())
            data['road_sha256'] = '0'*64
            path.write_text(json.dumps(data)+'\\n')
            with self.assertRaisesRegex(ValueError,'source hash differs'):
                check(target,DISTANCE,CANDIDATE)
'''


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    folder = CASE/'runtime-draft'
    folder.mkdir(exist_ok=True)
    cases = []
    for distance in DISTANCES:
        case_id = CASE.name+'__'+str(distance)
        plans = []
        for candidate in CANDIDATES:
            bundle = CASE/'offline/bundles'/str(distance)/candidate
            files = [{'path': name, 'content': (bundle/name).read_text()} for name in FILES]
            files.append({'path': 'tests/test_exact.py', 'content': TEST})
            construction = {'case_id': case_id, 'cell_id': 'C102951',
                            'law_id': 'NRS-484B-213-1', 'actor': 'motor_vehicle_driver',
                            'entrypoint': 'runner.py', 'files': files,
                            'status': 'unselected_cpu_diagnostic',
                            'recording_description': f'{distance} m requested oncoming separation; actual visibility, pass, interference and original pixels unverified.'}
            path = folder/f'{distance}-{candidate}-construction.json'
            path.write_text(json.dumps(construction, indent=2, allow_nan=False)+'\n')
            plans.append({'id': candidate, 'construction': str(path.relative_to(CASE)),
                          'construction_sha256': sha(path)})
        cases.append({'case_id': case_id,
                      'construction': plans[0]['construction'],
                      'construction_sha256': plans[0]['construction_sha256'],
                      'candidates': plans[1:],
                      'candidate_risk': {'status': 'physical',
                          'reason': 'Original hill-crest sightline and passing motion unverified'}})
    manifest = {'format': 'worker-unselected-draft-construction-manifest-v1',
                'assignment_id': CASE.name, 'status': 'draft_not_selected',
                'cases': cases,
                'original_native_observed': False, 'delivery_ready': False}
    output = CASE/'draft-execution-manifest.json'
    output.write_text(json.dumps(manifest, indent=2, allow_nan=False)+'\n')
    return {'construction_count': len(DISTANCES)*len(CANDIDATES),
            'manifest_sha256': sha(output)}


if __name__ == '__main__':
    print(json.dumps(build()))
