"""Build source-bound, deliberately unselected exact caravan construction drafts."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AID = 'training__C228508__NRS-484B-127-3__motor_vehicle_driver'
CAMERAS = [
    {'name': 'overview', 'width': 1920, 'height': 1080, 'pose_strategy': 'elevated view of full three-position caravan and potential entrant', 'fov_deg': 100},
    {'name': 'approach', 'width': 1280, 'height': 720, 'pose_strategy': 'forward approach view of consecutive caravan bodies', 'fov_deg': 95},
    {'name': 'reference_corner', 'width': 1280, 'height': 720, 'pose_strategy': 'rear quarter body extent and entry-gap view', 'fov_deg': 95},
    {'name': 'driver_reference', 'width': 1280, 'height': 720, 'pose_strategy': 'driver proxy view toward leading body and entrant', 'fov_deg': 90},
]
TEST = '''import json\nimport sys\nimport unittest\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).resolve().parents[1]))\nfrom runner import check\nfrom engineering import commanded_centers, clear_spaces, FRAMES, GAP_TARGETS_M, CANDIDATES\n\nclass Construction(unittest.TestCase):\n    def test_exact_case_and_candidate(self):\n        config=json.loads((Path(__file__).resolve().parents[1]/'config.json').read_text())\n        result=check(config)\n        self.assertEqual(result['engineering']['frames'],600)\n        self.assertTrue(result['camera_capture_implemented'])\n        suffix=config['case_suffix'];candidate=config['candidate_id']\n        for frame in (0,299,599):\n            gaps=clear_spaces(commanded_centers(suffix,candidate,frame))\n            self.assertTrue(all(abs(v-GAP_TARGETS_M[suffix])<1e-8 for v in gaps.values()))\n        self.assertEqual(len(CANDIDATES),2)\n        self.assertEqual(FRAMES,600)\n\nif __name__=='__main__': unittest.main()\n'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


entries = []
for suffix in ('probe_a', 'probe_b'):
    case_id = AID + '__' + suffix
    choices = {}
    for candidate in ('primary', 'fallback1'):
        config = {'case_id': case_id, 'selected_case_id': case_id,
                  'case': {'case_id': case_id}, 'case_suffix': suffix,
                  'candidate_id': candidate, 'cell_id': 'C228508',
                  'law_id': 'NRS-484B-127-3', 'actor': 'motor_vehicle_driver',
                  'duration_s': 30, 'rate_hz': 20, 'camera_plan_status': 'draft_unselected',
                  'cameras': CAMERAS,
                  'required_atoms': ['kin.speed', 'rel.surface_gap', 'rel.same_direction'],
                  'source_packets': [],
                  'recording_description': {'status': 'source_camera_acquisition_authored_cpu_unverified',
                      'channels': ['original actor bodies', 'caravan status', 'combination extent',
                                   'legal region', 'potential entrant', 'four camera frame joins'],
                      'physical_claimed': False}}
        files = []
        for filename in ('runner.py', 'engineering.py', 'geometry.py', 'finalize.py'):
            source = ROOT / 'native' / filename
            files.append({'path': filename, 'source': str(source), 'content': source.read_text()})
        files += [{'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'},
                  {'path': 'tests/test_draft.py', 'content': TEST}]
        proposal = {'case_id': case_id, 'cell_id': 'C228508', 'law_id': 'NRS-484B-127-3',
                    'actor': 'motor_vehicle_driver', 'entrypoint': 'runner.py',
                    'files': files, 'recording_description': config['recording_description'],
                    'candidate_id': candidate,
                    'status': 'unselected_native_draft_no_selected_saved_processing'}
        path = ROOT / 'cases' / suffix / candidate / 'construction.json'
        dump(path, proposal)
        choices[candidate] = {'construction': str(path.relative_to(ROOT)),
                              'construction_sha256': sha(path)}
    entries.append({'case_id': case_id, **choices['primary'],
                    'candidate_risk': {'status': 'physical',
                        'reason': 'A multi-actor combination and both adjacent entry gaps may drift under Native velocity control.'},
                    'candidates': [{'id': 'fallback1', **choices['fallback1'],
                        'trigger': {'source': 'original Native consecutive-body rows',
                            'metric': 'minimum_realized_group_clearance_m',
                            'failure_condition': 'body clearance or lane identity fails the predeclared target before comparison'},
                        'changed_knobs': ['group_speed_request_mps: 6.0 to 5.0 in both linked cases']}],
                    'selected_delivery': False})

manifest = {'format': 'worker-unselected-caravan-construction-draft-v1',
            'assignment_id': AID, 'cases': entries,
            'limitations': ['Four-camera acquisition is authored but not physically run or decoded; no selected saved processing or Native seal yet',
                            'Trailer proxy is not a physically coupled tow',
                            'No Native, legal-region, caravan-membership or entry-without-danger evidence claimed']}
dump(ROOT / 'draft-construction-manifest.json', manifest)
print(json.dumps({'manifest_sha256': sha(ROOT / 'draft-construction-manifest.json'),
                  'candidate_paths': len(entries) * 2}))
