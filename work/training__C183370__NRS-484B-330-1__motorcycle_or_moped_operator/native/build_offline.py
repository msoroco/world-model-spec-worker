"""Bundle exact flagger requests for pinned offline construction checks."""

import hashlib
import json
from pathlib import Path
from build_requests import CAMERAS


ROOT = Path(__file__).resolve().parent.parent
NATIVE = ROOT / 'native'
ASSIGNMENT = ROOT.name
SOURCE = Path('inputs') / ASSIGNMENT / 'assignment.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')


def build(repo=Path('.')):
    repo = Path(repo).resolve()
    common_files = []
    for local, path in [('runner.py', NATIVE / 'runner.py'),
                        ('check_requests.py', NATIVE / 'check_requests.py'),
                        (str(SOURCE), repo / SOURCE)]:
        common_files.append({'path': local, 'content': path.read_text()})
    for suffix in ('probe_a', 'probe_b', 'probe_c', 'probe_d'):
        for name in ('config.json', 'road.xodr', 'requested-tracks.jsonl'):
            local = suffix + '/' + name
            common_files.append({'path': local,
                                 'content': (NATIVE / local).read_text()})
    common_files.append({'path': 'tests/test_offline.py', 'content':
        'import unittest\nfrom check_requests import check_pair,read_case\n'
        'class FlaggedConstruction(unittest.TestCase):\n'
        ' def test_exact_pair(self):\n'
        '  self.assertEqual(check_pair()["crossing_frames"],[1350,1200])\n'
        ' def test_each_case(self):\n'
        '  self.assertEqual(len(read_case("probe_a")[1]),600)\n'
        '  self.assertEqual(len(read_case("probe_b")[1]),600)\n'
        '  self.assertEqual(check_pair(pair=("probe_c","probe_d"))["crossing_frames"],[1350,1200])\n'
        '  self.assertEqual(len(read_case("probe_c")[1]),600)\n'
        '  self.assertEqual(len(read_case("probe_d")[1]),600)\n'})
    cases = []
    for suffix in ('probe_a', 'probe_b', 'probe_c', 'probe_d'):
        case_id = ASSIGNMENT + '__' + suffix
        files = common_files + [{'path': 'selected-case.json',
                                 'content': json.dumps({'suffix': suffix,
                                                        'case_id': case_id}) + '\n'}]
        construction = {
            'case_id': case_id, 'law_id': 'NRS-484B-330-1',
            'cell_id': 'C183370', 'actor': 'motorcycle_or_moped_operator',
            'entrypoint': 'runner.py', 'files': files,
            'recording_description': {
                'channels': [
                    {'name': 'flagger_signal_observation', 'unit': 'structured',
                     'sampling_rate_hz': 20,
                     'method': 'same-frame original signal-asset and flagger readback',
                     'time_window': '600 frames over 30 seconds',
                     'reference_frame': 'Native world frame and reviewed approach',
                     'uncertainty': 'Requested indication is distinct from visible original pixels'},
                    {'name': 'motorcycle_response', 'unit': 'structured',
                     'sampling_rate_hz': 20,
                     'method': 'original vehicle body, velocity and stop-line join',
                     'time_window': '600 frames over 30 seconds',
                     'reference_frame': 'Native world XY and marked stop line',
                     'uncertainty': '50 ms sampling; Native motion requires physical review'},
                    {'name': 'four_view_video', 'unit': 'FFV1 frames',
                     'sampling_rate_hz': 20,
                     'method': 'synchronized original ' + ', '.join(CAMERAS) + ' sources',
                     'time_window': '600 frames over 30 seconds',
                     'reference_frame': 'scene and motorcycle-mounted reference cameras',
                     'uncertainty': 'Original signal, zone and subject visibility require review'},
                ],
                'context_inputs': [
                    {'name': 'flagger_authority_and_governance', 'unit': 'structured',
                     'method': 'independent reviewed and sealed authority/signal source packet'},
                    {'name': 'statutory_location_basis', 'unit': 'structured',
                     'method': 'independent reviewed and sealed designation or work-area packet'},
                ],
                'limitations': [
                    'Original authorization, governing direction and signal meaning require local review',
                    'Requested controller behavior and synthetic fixtures do not establish legal compliance',
                ],
            },
            'status': 'draft_cpu_offline_only',
        }
        path = NATIVE / (suffix + '-construction.json')
        write(path, construction)
        cases.append({'case_id': case_id,
                      'construction': str(path.relative_to(ROOT)),
                      'construction_sha256': sha(path),
                      'candidate_risk': {'status': 'none',
                          'reason': 'No alternate construction is yet CPU-proven; '
                                    'original signal and camera visibility need review.'},
                      'candidates': []})
    manifest = {'format': 'worker-unselected-draft-construction-manifest-v1',
                'assignment_id': ASSIGNMENT, 'status': 'draft_not_selected',
                'cases': cases, 'delivery_ready': False,
                'original_native_observed': False}
    write(ROOT / 'draft-native-manifest.json', manifest)
    return manifest


if __name__ == '__main__':
    print(json.dumps({'cases': [entry['case_id'] for entry in build()['cases']]}))
