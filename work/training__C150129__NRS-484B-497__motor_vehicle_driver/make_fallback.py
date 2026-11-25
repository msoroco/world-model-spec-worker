"""Create same-case early-braking candidates for incomplete left-curb stopping."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD_THROTTLE = 'throttle=.18 if index < 210 else 0'
NEW_THROTTLE = 'throttle=.12 if index < 180 else 0'
OLD_BRAKE = 'brake=0 if index < 210 else 1'
NEW_BRAKE = 'brake=0 if index < 180 else 1'
OLD_HANDBRAKE = 'hand_brake=index >= 300'
NEW_HANDBRAKE = 'hand_brake=index >= 260'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].split('__')[-1]
        primary = json.loads((HERE / entry['construction']).read_text())
        fallback = json.loads(json.dumps(primary))
        runner = next(f for f in fallback['files'] if f['path'] == 'runner.py')
        code = runner['content']
        for before, after in ((OLD_THROTTLE, NEW_THROTTLE),
                              (OLD_BRAKE, NEW_BRAKE),
                              (OLD_HANDBRAKE, NEW_HANDBRAKE)):
            if code.count(before) != 1:
                raise ValueError('Primary Native controller changed: ' + before)
            code = code.replace(before, after)
        runner['content'] = code
        fallback['candidate_id'] = 'fallback1'
        fallback['mechanisms'] = list(primary['mechanisms']) + [
            'Early low-throttle braking extends original measured left-rest interval']
        path = HERE / 'candidates' / suffix / 'fallback1' / 'construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(fallback, indent=2) + '\n')
        entry['candidate_risk'] = {
            'status': 'physical',
            'reason': 'Primary vehicle may fail to reach at least 100 original frames at rest fully within the left curb shoulder'}
        entry['candidates'] = [{
            'id': 'fallback1',
            'construction': str(path.relative_to(HERE)),
            'construction_sha256': sha(path),
            'trigger': {'source': 'original Native result.json and vehicle-pose.jsonl',
                        'metric': 'fully_left_rest_candidate_frames count in 600 original frames',
                        'failure_condition': 'fewer than 100 fully left rest frames or stop did not complete'},
            'changed_knobs': ['throttle reduced from 0.18 to 0.12',
                              'service brake begins at frame 180 instead of 210',
                              'hand brake begins at frame 260 instead of 300']}]
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    (HERE / 'selected-parking-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'fallbacks': len(manifest['cases']),
                      'construction_sha256': [c['candidates'][0]['construction_sha256']
                                              for c in manifest['cases']]}))


if __name__ == '__main__':
    main()
