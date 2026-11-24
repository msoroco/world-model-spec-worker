"""Add a shared controller-gain fallback for measured Native speed shortfall."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


manifest_path = HERE / 'execution-manifest.json'
manifest = json.loads(manifest_path.read_text())
for name, entry in zip(('below', 'above'), manifest['cases']):
    primary = json.loads((HERE / entry['construction']).read_text())
    runner = next(item for item in primary['files'] if item['path'] == 'runner.py')
    old = 'throttle = min(1.0, max(0.0, (target - speed) * .35))'
    new = 'throttle = min(1.0, max(0.0, (target - speed) * .55))'
    if runner['content'].count(old) != 1:
        raise ValueError('Expected one shared speed-controller knob')
    runner['content'] = runner['content'].replace(old, new)
    primary['status'] = 'partial_fallback_cpu_diagnostic_physical_unverified'
    config = next(item for item in primary['files'] if item['path'] == 'config.json')
    data = json.loads(config['content'])
    data['status'] = primary['status']
    config['content'] = json.dumps(data, indent=2, sort_keys=True) + '\n'
    relative = f'selected-candidates/{name}/fallback1/construction.json'
    path = HERE / relative
    write(path, primary)
    entry['candidate_risk'] = {
        'status': 'physical',
        'reason': 'Native speed can fall short of the requested rate on the roundabout arc or exit; controller gain is selectable only after measured original-source failure.'}
    entry['candidates'] = [{
        'id': 'fallback1',
        'construction': relative,
        'construction_sha256': sha(path),
        'trigger': {
            'source': 'original Native post-tick velocity and controller request on frames 100..499',
            'metric': 'median_requested_minus_measured_mph',
            'failure_condition': 'median_requested_minus_measured_mph > 2.0 for at least 50 consecutive arc frames'},
        'changed_knobs': ['throttle_proportional_gain_0.35_to_0.55'],
        'preparation_status': 'fallback_cpu_reproof_pending'}]
manifest['status'] = 'partial_primary_cpu_proven_fallback_reproof_pending'
write(manifest_path, manifest)
print(sha(manifest_path))
