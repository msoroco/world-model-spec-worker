"""Retain five source-bound current-runtime positive/missing-source receipts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def main():
    path = HERE / 'draft-native-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        slug = entry['case_id'].rsplit('__', 1)[1]
        source = REPO / '.runtime-work' / ('c386328-compat-' + slug.replace('_', '') + '-v6')
        receipt_path = source / 'compatibility.json'
        if not receipt_path.is_file():
            raise ValueError('Current-runtime compatibility proof missing: ' + slug)
        receipt = json.loads(receipt_path.read_text())
        for original, target in (('compatibility-analysis.log', 'cpu-compat-' + slug + '-analysis.log'),
                                 ('negative-analysis.log', 'cpu-compat-' + slug + '-negative.log')):
            (HERE / target).write_text((source / original).read_text().rstrip() + '\n')
        receipt['log_sha256'] = sha(HERE / ('cpu-compat-' + slug + '-analysis.log'))
        receipt['negative_log_sha256'] = sha(HERE / ('cpu-compat-' + slug + '-negative.log'))
        copy = HERE / ('cpu-compat-' + slug + '.json')
        put(copy, receipt)
        entry['compatibility'] = {'receipt': copy.name, 'sha256': sha(copy),
                                  'log': 'cpu-compat-' + slug + '-analysis.log'}
        entry['negative'] = {'log': 'cpu-compat-' + slug + '-negative.log'}
        entry['acquisition'] = {channel['name']: {
            'entrypoint': 'finalize.py',
            'method': 'source-hashed original Native sign, actor body, civil-time and four-camera join with independent full-interval review',
            'evidence': 'channels/' + channel['name'] + '.jsonl'}
            for channel in entry['recording_description']['channels']}
    put(path, manifest)
    return {'cases': len(manifest['cases']), 'manifest_sha256': sha(path)}


if __name__ == '__main__':
    print(json.dumps(main(), sort_keys=True))
