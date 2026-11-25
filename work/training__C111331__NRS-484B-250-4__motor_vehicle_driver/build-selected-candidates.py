"""Bind repaired signal geometry and original-source finalizer into exact candidates."""
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BASE = ROOT.name


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


cases = []
for n, label in ((1, 'primary'), (2, 'contrast')):
    exact = f'{BASE}__controlled_{n}'
    source = json.loads((ROOT / f'selected-v3-{label}-construction.json').read_text())
    candidates = []
    for name, shift in (('primary', 0), ('fallback1', 2.0)):
        item = copy.deepcopy(source)
        item['status'] = 'selected_cpu_construction_in_progress'
        signal_file = next(f for f in item['files'] if f['path'] == 'native_signal.py')
        signal_file['content'] = (ROOT / 'native/signal_readback.py').read_text()
        config_file = next(f for f in item['files'] if f['path'] == 'config.json')
        config = json.loads(config_file['content'])
        config.update(candidate_id=name, spawn_shift_m=shift,
                      status='selected_cpu_construction_in_progress')
        config_file['content'] = json.dumps(config, indent=2, sort_keys=True) + '\n'
        path = ROOT / 'selected-candidates' / f'controlled_{n}' / name / 'construction.json'
        write(path, item)
        candidates.append((name, path.relative_to(ROOT).as_posix(), sha(path)))
    cases.append({'case_id': exact, 'id': f'controlled_{n}',
                  'kind': 'draft_not_selected',
                  'construction': candidates[0][1],
                  'construction_sha256': candidates[0][2],
                  'fixture_recipe': f'work/{BASE}/selected-v3-{label}-fixture-recipe.json',
                  'measurement_contract': f'selected-v3-{label}-measurement-contract.json',
                  'measurement_procedure': {'entrypoint': 'finalize.py'},
                  'candidate_risk': {'status': 'physical',
                      'reason': 'Primary ego spawn may be obstructed on Native map import'},
                  'candidates': [{'id': candidates[1][0],
                      'construction': candidates[1][1],
                      'construction_sha256': candidates[1][2],
                      'changed_knobs': ['spawn_shift_m: 0 to 2.0'],
                      'trigger': {'source': 'native-map-readback.json and capture report',
                                  'metric': 'ego approach spawn clearance',
                                  'failure_condition': 'Primary spawn obstructed or outside lane'}}]})
write(ROOT / 'selected-construction-manifest.json',
      {'format': 'worker-unselected-draft-construction-manifest-v1',
       'assignment_id': BASE, 'status': 'selected_cpu_construction_in_progress',
       'delivery_ready': False, 'original_native_observed': False,
       'runtime_manifest_sha256': json.loads((ROOT / 'selected-v3-primary-manifest.json').read_text())['runtime_manifest_sha256'],
       'cases': cases})
