"""Author one shared lower-speed braking alternative for both street probes."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
BEFORE_THROTTLE = 'throttle = .28 if distance > 9 else (.11 if distance > 4 else 0)'
AFTER_THROTTLE = 'throttle = .20 if distance > 11 else (.08 if distance > 5 else 0)'
BEFORE_BRAKE = 'brake = 0 if distance > 4 else (1 if distance < 2 else .35)'
AFTER_BRAKE = 'brake = 0 if distance > 5 else (1 if distance < 2.5 else .45)'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest_path = HERE / 'selected-parking-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for number, entry in enumerate(manifest['cases'], 1):
        source = HERE / entry['construction']
        proposal = json.loads(source.read_text())
        files = {item['path']: item for item in proposal['files']}
        runner = files['runner.py']['content']
        if runner.count(BEFORE_THROTTLE) != 1 or runner.count(BEFORE_BRAKE) != 1:
            raise ValueError('Primary parking controller changed; inspect before rebuilding fallback')
        files['runner.py']['content'] = runner.replace(BEFORE_THROTTLE, AFTER_THROTTLE).replace(
            BEFORE_BRAKE, AFTER_BRAKE)
        config = json.loads(files['config.json']['content'])
        if config.get('candidate_id') != 'primary':
            raise ValueError('Primary candidate ID changed')
        config['candidate_id'] = 'fallback1'
        files['config.json']['content'] = json.dumps(config, indent=2) + '\n'
        proposal['mechanisms'].append(
            'fallback1 uses lower approach throttle and earlier braking for the same requested parking segment')
        relative = f'cases/controlled_{number}/fallback1/construction.json'
        target = HERE / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(proposal, indent=2) + '\n')
        entry['candidates'] = [{
            'id': 'fallback1', 'construction': relative,
            'construction_sha256': sha(target),
            'trigger': {'source': 'original Native vehicle-poses.jsonl and result.json',
                        'metric': 'parking target occupancy and terminal speed proxy',
                        'failure_condition': 'primary overshoots the requested segment or lacks a stationary interval'},
            'changed_knobs': ['shared approach throttle .28/.11 to .20/.08',
                              'shared braking entry from 4 m to 5 m and stronger intermediate brake'],
        }]
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({entry['case_id']: entry['candidates'][0]['construction_sha256']
                      for entry in manifest['cases']}, sort_keys=True))


if __name__ == '__main__':
    main()
