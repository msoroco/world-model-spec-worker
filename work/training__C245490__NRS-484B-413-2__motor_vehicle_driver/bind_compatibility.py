"""Bind current-runtime positive and missing-source public receipts to exact cases."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    path = HERE / 'draft-native-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        source = REPO / '.runtime-work' / ('c245490_compat_v7_' + suffix)
        receipt = json.loads((source / 'compatibility.json').read_text())
        if not receipt.get('passed') or receipt.get('construction_sha256') != entry['construction_sha256']:
            raise ValueError('Current public proof missing or stale: ' + suffix)
        for original, target in (('compatibility-analysis.log', 'cpu-compat-' + suffix + '-analysis.log'),
                                 ('negative-analysis.log', 'cpu-compat-' + suffix + '-negative.log')):
            (HERE / target).write_text((source / original).read_text().rstrip() + '\n')
        receipt['log_sha256'] = sha(HERE / ('cpu-compat-' + suffix + '-analysis.log'))
        receipt['negative_log_sha256'] = sha(HERE / ('cpu-compat-' + suffix + '-negative.log'))
        copy = HERE / ('cpu-compat-' + suffix + '.json')
        copy.write_text(json.dumps(receipt, indent=2, allow_nan=False) + '\n')
        entry['compatibility'] = {'receipt': copy.name, 'sha256': sha(copy),
            'log': 'cpu-compat-' + suffix + '-analysis.log'}
        entry['negative'] = {'log': 'cpu-compat-' + suffix + '-negative.log'}
        entry['acquisition'] = {channel['name']: {
            'entrypoint': 'finalize.py',
            'method': 'source-hashed original Native signal, body, lane, weather and four-camera frame join',
            'evidence': 'channels/' + channel['name'] + '.jsonl'}
            for channel in entry['recording_description']['channels']}
    path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'cases': len(manifest['cases']), 'manifest_sha256': sha(path)}, sort_keys=True))


if __name__ == '__main__':
    main()
