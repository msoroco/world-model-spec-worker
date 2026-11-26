"""Bind exact selected CPU receipts without claiming a physical Native run."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[3]
AID = 'training__C394563__LVMC-11-18-020__motor_vehicle_driver'
FOLDER = ROOT / 'work' / AID

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

cases = []
for x in ('a', 'b'):
    case = AID + '__selected_1290826d__condition_' + x
    cons = 'selected-condition-' + x + '-construction.json'
    offline = 'native/condition-' + x + '-native-offline.log'
    compat = 'selected-compatibility/condition-' + x + '/'
    physical = 'proofs/physical-' + x + '/receipt.json'
    construction = json.loads((FOLDER / cons).read_text())
    channels = [c['name'] for c in construction['recording_description']['channels']]
    config = json.loads(next(f['content'] for f in construction['files'] if f['path'] == 'config.json'))
    required = set(config.get('required_atoms', [])) | set(channels)
    acquisition = {name: {'entrypoint': 'finalize.py',
                          'method': 'source-joined original Native actor/map/frame readback and four original camera streams',
                          'evidence': ['native_samples.jsonl', 'road_geometry.json', 'video_frames.jsonl',
                                       'overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv']}
                   for name in required}
    cases.append({'case_id': case, 'kind': 'delivery', 'construction': cons,
                  'construction_sha256': sha(FOLDER / cons),
                  'candidate_risk': {'status': 'none',
                                     'reason': 'The exact primary has a closed source-based failure rule. No distinct CPU-validated alternate is selected; a physical or semantic failure stops local adoption for review.'},
                  'candidates': [],
                  'measurement_procedure': {'entrypoint': 'finalize.py'},
                  'preparation_status': 'incomplete',
                  'measurement_contract': 'measurement-contract-condition-' + x + '.json',
                  'fixture_recipe': 'work/' + AID + '/native/recipe-condition-' + x + '.json',
                  'native_handoff': {'python_env_var': 'CARLA_PYTHON', 'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
                  'offline': {'exit_code': 0, 'construction_sha256': sha(FOLDER / cons),
                              'command': '.venv-cpu/bin/python runtime.py offline --manifest work/' + AID + '/native/native-draft-manifest.json --case ' + case + ' --output .runtime-work/c394563-native-' + x + '9',
                              'log': offline, 'log_sha256': sha(FOLDER / offline)},
                  'compatibility': {'receipt': compat + 'compatibility.json',
                                    'sha256': sha(FOLDER / (compat + 'compatibility.json')),
                                    'log': compat + 'compatibility-analysis.log',
                                    'negative_log': compat + 'negative-analysis.log'},
                  'negative': {'log': compat + 'negative-analysis.log',
                               'log_sha256': sha(FOLDER / (compat + 'negative-analysis.log'))},
                  'physical_preparation': {'receipt': physical, 'sha256': sha(FOLDER / physical)},
                  'acquisition': acquisition,
                  'post_capture': {'recorded_only': True,
                                   'command': 'runtime.py process-saved --manifest work/' + AID + '/execution-manifest.json --case ' + case + ' --attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library --validator $DECODER',
                                   'feedback_command': 'cat $SAVED_OUTPUT/feedback.json # ' + case,
                                   'test_log': 'proofs/saved-' + x + '.log',
                                   'test_log_sha256': '', 'test_exit_code': 0}})
manifest = {'format': 'worker-execution-manifest', 'assignment_id': AID,
            'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'), 'cases': cases}
(FOLDER / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
print('execution manifest skeleton written')
