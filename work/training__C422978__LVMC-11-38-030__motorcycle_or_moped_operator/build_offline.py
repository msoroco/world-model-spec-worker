"""Materialize eight exact unselected C422978 CPU construction bundles."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]
NATIVE = FOLDER / 'native'
AID = FOLDER.name
TEST = '''import json
from pathlib import Path
import unittest
from runner import check


class SidewalkConstructionTests(unittest.TestCase):
    def test_exact_case(self):
        config = json.loads(Path('config.json').read_text())
        result = check(Path('.'), config['case_suffix'], config['candidate_id'])
        self.assertTrue(result['passed'])
        self.assertEqual(result['track_rows'], 480)
        self.assertFalse(result['carla_imported'])

    def test_case_swap_rejected(self):
        config = json.loads(Path('config.json').read_text())
        wrong = 'witness_2' if config['case_suffix'] == 'witness_1' else 'witness_1'
        with self.assertRaises(ValueError):
            check(Path('.'), wrong, config['candidate_id'])

    def test_unsupported_candidate_rejected(self):
        config = json.loads(Path('config.json').read_text())
        with self.assertRaises(ValueError):
            check(Path('.'), config['case_suffix'], 'unsupported')


if __name__ == '__main__':
    unittest.main()
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def build():
    batch = json.loads((ROOT / 'batch.json').read_text())
    draft = json.loads((NATIVE / 'drafts/manifest.json').read_text())
    manifest = {'format': 'worker-unselected-draft-construction-manifest-v1',
                'assignment_id': AID, 'status': 'draft_not_selected',
                'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
                'cases': []}
    assignment = (ROOT / 'inputs' / AID / 'assignment.json').read_text()
    road = (NATIVE / 'road.xodr').read_text()
    runner = (NATIVE / 'runner.py').read_text()
    triggers = (NATIVE / 'triggers.py').read_text()
    saved_meter = (NATIVE / 'measure_saved.py').read_text()
    finalizer = (NATIVE / 'finalize.py').read_text()
    for case in ('witness_1', 'witness_2'):
        case_id = AID + '__' + case
        entry = {'case_id': case_id, 'kind': 'draft_not_selected',
                 'measurement_contract': 'native/measurement-contract.json',
                 'measurement_procedure': {'entrypoint': 'finalize.py',
                                           'output_schema': 'c422978-sidewalk-analysis-v1'},
                 'candidate_risk': {'status': 'physical',
                                    'reason': 'Original Native sidewalk lane, motorcycle body and four cameras unverified'},
                 'candidates': []}
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            source = NATIVE / 'drafts' / case / candidate
            config = json.loads((source / 'config.json').read_text())
            config['case_suffix'] = case
            config['required_atoms'] = ['kin.velocity', 'rel.occupies']
            files = [{'path': name, 'content': content} for name, content in (
                ('runner.py', runner), ('triggers.py', triggers),
                ('measure_saved.py', saved_meter),
                ('finalize.py', finalizer),
                ('assignment-source.json', assignment), ('authored-road.xodr', road),
                ('requested-tracks.jsonl', (source / 'requested-tracks.jsonl').read_text()),
                ('config.json', json.dumps(config, indent=2) + '\n'),
                ('tests/test_construction.py', TEST))]
            construction = {'case_id': case_id, 'cell_id': 'C422978',
                            'law_id': 'LVMC-11-38-030', 'actor': 'motorcycle_or_moped_operator',
                            'entrypoint': 'runner.py', 'files': files,
                            'measurement_plan': {'status': 'original_saved_measurement_pending',
                                                 'method': 'Native motorcycle full-body occupancy of surveyed sidewalk lane'},
                            'recording_description': {'channels': [
                                {'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
                                 'method': 'original Native actor and camera frame join',
                                 'time_window': 'entire 24 s attempt',
                                 'reference_frame': 'Native imported OpenDRIVE and original camera',
                                 'uncertainty': '50 ms frame bracket; legal context separately reviewed'}
                                for name in ('motorcycle_body_speed', 'sidewalk_lane_readback', 'camera_frame_join')],
                                'context_inputs': [],
                                'limitations': ['Authored requests are not Native observations']},
                            'status': 'unselected_cpu_draft'}
            relative = f'draft-candidates/{case}/{candidate}/construction.json'
            target = FOLDER / relative
            write(target, construction)
            ref = {'id': candidate, 'construction': relative,
                   'construction_sha256': sha(target)}
            if candidate == 'primary':
                entry.update(ref)
            else:
                ref['trigger'] = {'source': 'source-hashed saved original body or camera packet',
                                  'method': draft['entries'][4 * ('witness_1', 'witness_2').index(case)
                                                           + ('primary','fallback1','fallback2','fallback3').index(candidate)]['trigger']}
                ref['changed_knobs'] = {'fallback1': ['lateral_start_frame'],
                                        'fallback2': ['lateral_duration_frames'],
                                        'fallback3': ['camera_fov_deg']}[candidate]
                entry['candidates'].append(ref)
        manifest['cases'].append(entry)
    write(FOLDER / 'draft-execution-manifest.json', manifest)
    write(FOLDER / 'proposals/cases.json', {
        'cell_id': 'C422978', 'actor': 'motorcycle_or_moped_operator',
        'status': 'unselected_cpu_draft',
        'cases': [{'case_id': entry['case_id'],
                   'target_law_id': 'LVMC-11-38-030', 'target_type': 'attempt',
                   'recording_description': json.loads(
                       (FOLDER / entry['construction']).read_text())['recording_description']}
                  for entry in manifest['cases']]})
    return manifest


if __name__ == '__main__':
    print(json.dumps({'cases': len(build()['cases']), 'bundles': 8}))
