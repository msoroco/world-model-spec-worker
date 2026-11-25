"""Author a lower-speed earlier-braking fallback for each selected case."""
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
BEFORE_THROTTLE = 'throttle = .28 if distance > 9 else (.11 if distance > 4 else 0.0)'
AFTER_THROTTLE = 'throttle = .20 if distance > 11 else (.08 if distance > 5 else 0.0)'
BEFORE_BRAKE = 'brake = 0.0 if distance > 4 else (1.0 if distance < 2 else .35)'
AFTER_BRAKE = 'brake = 0.0 if distance > 5 else (1.0 if distance < 2.5 else .45)'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        source = HERE / entry['construction']
        proposal = json.loads(source.read_text())
        files = {item['path']: item for item in proposal['files']}
        runner = files['runner.py']['content']
        if runner.count(BEFORE_THROTTLE) != 1 or runner.count(BEFORE_BRAKE) != 1:
            raise ValueError('Primary controller changed: ' + suffix)
        files['runner.py']['content'] = runner.replace(BEFORE_THROTTLE, AFTER_THROTTLE).replace(
            BEFORE_BRAKE, AFTER_BRAKE)
        config = json.loads(files['config.json']['content'])
        if config.get('candidate_id') != 'primary':
            raise ValueError('Primary candidate identity changed')
        config['candidate_id'] = 'fallback1'
        files['config.json']['content'] = json.dumps(config, indent=2) + '\n'
        proposal['mechanisms'].append('Fallback uses lower approach throttle and earlier braking for the same requested target.')
        relative = f'fallbacks/{suffix}/fallback1/construction.json'
        target = HERE / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(proposal, indent=2) + '\n')
        entry['candidates'] = [{
            'id': 'fallback1', 'construction': relative,
            'construction_sha256': sha(target),
            'trigger': {'source': 'original Native vehicle-poses.jsonl and result.json',
                        'metric': 'terminal body gap and sampled halt span',
                        'failure_condition': 'primary overshoots the requested body gap or lacks a five-second stationary proxy'},
            'changed_knobs': ['approach throttle .28/.11 to .20/.08',
                              'braking entry 4 m to 5 m and intermediate brake .35 to .45']}]
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({e['case_id']: e['candidates'][0]['construction_sha256'] for e in manifest['cases']}, sort_keys=True))


if __name__ == '__main__':
    main()
