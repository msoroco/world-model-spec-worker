"""One shared stronger steering response for failed original left-turn progress."""
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    primary_code = (ROOT / 'runner.py').read_text()
    if primary_code.count('error/45') != 1:
        raise ValueError('primary steering gain anchor changed')
    fallback_code = primary_code.replace('error/45', 'error/35')
    source = ROOT / 'fallback_runner.py'
    source.write_text(fallback_code)
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        primary = json.loads((ROOT / entry['construction']).read_text())
        fallback = copy.deepcopy(primary)
        runner = next(item for item in fallback['files'] if item['path'] == 'runner.py')
        runner['content'] = fallback_code
        runner['source'] = str(source.relative_to(REPO))
        path = ROOT / ('fallback-' + suffix + '-construction.json')
        path.write_text(json.dumps(fallback, indent=2) + '\n')
        prior = next((c for c in entry.get('candidates', [])
                      if c.get('id') == 'fallback1' and
                      c.get('construction_sha256') == sha(path)), {})
        candidate = {'id': 'fallback1', 'construction': path.name,
            'construction_sha256': sha(path),
            'trigger': {'source': 'original Native turn-history.jsonl and trace.jsonl',
                'metric': '30 s sampled left-turn heading change and travel progress',
                'failure_condition': 'primary left turn has heading change below 45 degrees or travel progress below 5 m'},
            'changed_knobs': ['bounded route steering error divisor: 45 -> 35 degrees']}
        for key in ('offline', 'compatibility'):
            if key in prior:
                candidate[key] = prior[key]
        entry['candidate_risk'] = {'status': 'physical',
            'reason': 'The simple bounded steering gain may not complete the connected left turn before the 30 s capture ends.'}
        entry['candidates'] = [candidate]
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    main()
