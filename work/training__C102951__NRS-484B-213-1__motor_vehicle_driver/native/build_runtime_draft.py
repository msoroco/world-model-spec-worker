"""Pin the 120 m primary request to the current runtime offline check."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASE = HERE.parent
BUNDLE = CASE/'offline/bundles/120/primary'
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

class ExactPassingRequest(unittest.TestCase):
    def test_600_frame_primary_and_four_cameras(self):
        result = check(Path.cwd(), 120, 'primary')
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
                check(target,120,'primary')
'''


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    case_id = CASE.name+'__120'
    files = [{'path': name, 'content': (BUNDLE/name).read_text()} for name in FILES]
    files.append({'path': 'tests/test_exact.py', 'content': TEST})
    construction = {'case_id': case_id, 'cell_id': 'C102951',
                    'law_id': 'NRS-484B-213-1', 'actor': 'motor_vehicle_driver',
                    'entrypoint': 'runner.py', 'files': files,
                    'status': 'unselected_cpu_diagnostic',
                    'recording_description': '120 m requested oncoming separation; actual visibility, pass, interference and original pixels unverified.'}
    folder = CASE/'runtime-draft'
    folder.mkdir(exist_ok=True)
    path = folder/'120-primary-construction.json'
    path.write_text(json.dumps(construction, indent=2, allow_nan=False)+'\n')
    manifest = {'format': 'worker-unselected-draft-construction-manifest-v1',
                'assignment_id': CASE.name, 'status': 'draft_not_selected',
                'cases': [{'case_id': case_id,
                           'construction': str(path.relative_to(CASE)),
                           'construction_sha256': sha(path),
                           'candidates': [],
                           'candidate_risk': {'status': 'physical',
                               'reason': 'Original hill-crest sightline and passing motion unverified'}}],
                'original_native_observed': False, 'delivery_ready': False}
    output = CASE/'draft-execution-manifest.json'
    output.write_text(json.dumps(manifest, indent=2, allow_nan=False)+'\n')
    return {'construction_sha256': sha(path), 'manifest_sha256': sha(output)}


if __name__ == '__main__':
    print(json.dumps(build()))
