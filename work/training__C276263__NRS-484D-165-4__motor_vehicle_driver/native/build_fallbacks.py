"""Build one same-case parking-position fallback per beam request."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AID = ROOT.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    manifest_path = ROOT / 'selected-draft-execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        primary = json.loads((ROOT / entry['construction']).read_text())
        fallback = json.loads(json.dumps(primary))
        files = {f['path']: f for f in fallback['files']}
        source = files['runner.py']['content']
        if source.count('4.85') < 2:
            raise ValueError('Expected parked pose and waypoint not found')
        files['runner.py']['content'] = source.replace('4.85', '5.50')
        config = json.loads(files['config.json']['content'])
        config['candidate_id'] = 'fallback1'
        files['config.json']['content'] = json.dumps(config, indent=2, ensure_ascii=False) + '\n'
        fallback['fallback_note'] = (
            'Move parked pose and waypoint 0.65 m along the same curb lane to improve beam and body visibility; '
            'keep lamp state and all case observations unchanged.')
        path = ROOT / ('selected-' + suffix + '-fallback1-construction.json')
        write(path, fallback)
        entry['candidates'] = [{
            'id': 'fallback1', 'construction': path.name,
            'construction_sha256': sha(path),
            'trigger': {'source': 'original Native camera coverage review',
                        'metric': 'joined body and beam pixels visible in all 600 frames',
                        'failure_condition': 'primary parked pose has occluded beam or incomplete parked body visibility'},
            'changed_knobs': ['parked pose and waypoint x coordinate 4.85 m to 5.50 m on the same curb lane']}]
    write(manifest_path, manifest)
    print(json.dumps({'fallbacks': len(manifest['cases']),
                      'constructions': [(e['case_id'], e['candidates'][0]['construction_sha256'])
                                        for e in manifest['cases']]}))


if __name__ == '__main__':
    main()
