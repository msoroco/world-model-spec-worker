"""Package the 600-frame reference request for the pinned offline materializer."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BUNDLE = HERE/'offline/reference/primary'
CASE_ID = HERE.name+'__reference'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')


def build():
    names = ('assignment-source.json', 'case-plan.json', 'road.xodr',
             'config.json', 'requested-tracks.jsonl', 'measure_saved.py',
             'measure_camera.py', 'measure_context.py', 'prepare_context.py',
             'measure_exception.py', 'measurement-contract.json', 'triggers.py')
    files = [{'path': name, 'content': (BUNDLE/name).read_text()} for name in names if name != 'config.json']
    config = json.loads((BUNDLE/'config.json').read_text())
    config.update(selected_case_id=CASE_ID, required_atoms=[], source_packets=[],
                  case={'case_id': CASE_ID},
                  cameras=['overview', 'approach', 'reference_corner', 'driver_reference'],
                  supported_case_ids=[CASE_ID])
    files.append({'path': 'config.json', 'content': json.dumps(config, indent=2, sort_keys=True)+'\n'})
    files.append({'path': 'finalize.py', 'content': (HERE/'native/finalize_v2.py').read_text()})
    files.append({'path': 'legacy_runner.py', 'content': (BUNDLE/'runner.py').read_text()})
    files.append({'path': 'runner.py', 'content': '''"""CPU entry for the exact reference primary Native request."""
import argparse
import json
from pathlib import Path
from legacy_runner import check

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if not args.check:
        raise ValueError('Draft CPU package does not dispatch Native capture')
    print(json.dumps(check(Path(__file__).resolve().parent, 'reference', 'primary')))
'''})
    files.append({'path': 'tests/test_cpu.py', 'content': '''import json
from pathlib import Path
import unittest
from legacy_runner import check


class ExactRequestTest(unittest.TestCase):
    def test_reference_primary_request(self):
        bundle = Path(__file__).resolve().parents[1]
        result = check(bundle, 'reference', 'primary')
        self.assertTrue(result['passed'])
        self.assertEqual(result['requested_frames'], 600)
        self.assertFalse(result['original_native_observed'])

    def test_construction_hashes(self):
        bundle = Path(__file__).resolve().parents[1]
        config = json.loads((bundle/'config.json').read_text())
        self.assertEqual(config['duration_s'], 30)
        self.assertEqual(config['case_id'], 'training__C422978__NRS-484B-117-1__heavy_vehicle_driver__reference')


if __name__ == '__main__':
    unittest.main()
'''})
    channels = [{'name': name, 'unit': 'structured', 'sampling_rate_hz': 20,
                 'method': 'Retained source-bound 600-frame Native diagnostic rows',
                 'time_window': 'entire 30 s / 600 frame attempt',
                 'reference_frame': 'original Native frame and time',
                 'uncertainty': '50 ms frame bracket; physical and legal review pending'}
                for name in ('subject_pose_body_speed', 'sidewalk_occupancy')]
    recording = {'channels': channels, 'context_inputs': [],
                 'limitations': ['Synthetic CPU source only; no original City or Native qualification']}
    construction = {'case_id': CASE_ID, 'cell_id': 'C422978',
                    'law_id': 'NRS-484B-117-1', 'actor': 'heavy_vehicle_driver',
                    'entrypoint': 'runner.py', 'files': files,
                    'recording_description': recording,
                    'status': 'unselected_cpu_draft',
                    'original_native_observed': False}
    path = HERE/'v2-reference-primary-construction.json'
    write(path, construction)
    runtime = json.loads((HERE.parents[1]/'batch.json').read_text())
    manifest = {'format': 'worker-unselected-draft-construction-manifest-v1',
                'assignment_id': HERE.name, 'status': 'draft_not_selected',
                'runtime_manifest_sha256': runtime['runtime']['source_manifest_sha256'],
                'cases': [{'case_id': CASE_ID, 'kind': 'draft_not_selected',
                           'id': 'primary', 'construction': path.name,
                           'construction_sha256': digest(path),
                           'fixture_recipe': str((HERE/'v2-reference-primary-fixture-recipe.json').relative_to(HERE.parents[1])),
                           'measurement_contract': 'v2-reference-primary-measurement-contract.json',
                           'measurement_procedure': {'entrypoint': 'finalize.py'},
                           'recording_description': recording,
                           'candidates': [],
                           'candidate_risk': {'status': 'none',
                                              'reason': 'CPU offline probe only; physical risk review pending'}}]}
    write(HERE/'v2-reference-primary-draft-manifest.json', manifest)
    selected = [0, 1, 6]
    plan = json.loads((HERE/'case-plan.json').read_text())
    keys = ('sidewalk_overlap_frames', 'misdemeanor_context', 'reviewed_scope')
    methods = ('measure_sidewalk_overlap', 'measure_misdemeanor_context',
               'measure_reviewed_scope')
    types = ('number', 'object', 'object')
    inputs = ['native-observed.jsonl', 'native-map-readback.json',
              'native-capture-report.json', 'video_frames.jsonl',
              'capture/evidence.jsonl']
    contract = {'format': 'worker-measurement-contract', 'case_id': CASE_ID,
                'requirements': [
                    {'disposition_index': i,
                     'requirement': plan['requirement_dispositions'][i]['requirement'],
                     'source': plan['requirement_dispositions'][i]['source'],
                     'output_key': key, 'method': method,
                     'value_type': typ,
                     'kind': 'measured' if i != 1 else 'sourced_context',
                     'inputs': inputs}
                    for i, key, method, typ in zip(selected, keys, methods, types)],
                'negative': {'remove': ['native-observed.jsonl'],
                             'error_contains': 'Missing required source: native-observed.jsonl'},
                'status': 'unselected_contract_draft'}
    write(HERE/'v2-reference-primary-measurement-contract.json', contract)
    proposal = {'format': 'worker-case-proposals', 'cases': [
        {'case_id': CASE_ID, 'target_law_id': 'NRS-484B-117-1',
         'target_type': 'attempt', 'rationale': 'Unselected sidewalk reference diagnostic',
         'variable_assignments': {}, 'recording_description': recording}]}
    (HERE/'proposals').mkdir(exist_ok=True)
    proposal_path = HERE/'proposals/cases.json'
    if proposal_path.exists():
        existing = json.loads(proposal_path.read_text())
        others = [item for item in existing.get('cases', [])
                  if item['case_id'] != CASE_ID]
        proposal['cases'] = others + proposal['cases']
    write(proposal_path, proposal)
    return manifest


if __name__ == '__main__':
    print(json.dumps({'cases': len(build()['cases'])}))
