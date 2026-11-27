"""Risk-triggered earlier-brake fallback for every linked exact bus case."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        primary = json.loads((ROOT / entry['construction']).read_text())
        fallback = json.loads(json.dumps(primary))
        runner = next(item for item in fallback['files'] if item['path'] == 'runner.py')
        source = runner['content']
        for old, new in (("selection.get('candidate_id') != 'primary'", "selection.get('candidate_id') != 'fallback1'"),
                         ('remaining > 4:', 'remaining > 6:'),
                         ('throttle=.3', 'throttle=.23')):
            if old not in source:
                raise ValueError('Fallback control source changed: ' + old)
            source = source.replace(old, new)
        runner['content'] = source
        runner.pop('source', None)
        fallback['mechanisms'] = list(fallback['mechanisms']) + [
            'Fallback earlier brake initiation and lower approach throttle, only after original stopping-location failure']
        path = ROOT / 'cases' / suffix / 'fallback1' / 'construction.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(fallback, indent=2, ensure_ascii=False) + '\n')
        entry['candidates'] = [{'id': 'fallback1', 'construction': str(path.relative_to(ROOT)),
            'construction_sha256': sha(path),
            'trigger': {'source': 'bus-history.jsonl',
                        'metric': 'final source-joined occupied_zone_id and target distance_m',
                        'failure_condition': 'Primary bus overshoots surveyed target by more than 5 m or never occupies target zone'},
            'changed_knobs': ['approach throttle 0.30 to 0.23',
                              'braking onset 4 m to 6 m before target']}]
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print('Eight matched earlier-brake fallback constructions bound')


if __name__ == '__main__':
    main()
