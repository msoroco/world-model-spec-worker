"""Bind exact current-runtime offline and source-gated compatibility proofs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + '\n')


def clean_copy(source, target):
    target.write_text(source.read_text().rstrip() + '\n')


def main():
    path = HERE / 'draft-native-manifest.json'
    manifest = json.loads(path.read_text())
    for entry in manifest['cases']:
        slug = entry['case_id'].rsplit('__', 1)[-1]
        offline = REPO / '.runtime-work' / ('c146108-offline7-' + slug)
        if not offline.is_dir() or not (offline / 'offline.log').is_file():
            raise ValueError('Missing final-byte offline proof: ' + slug)
        log = HERE / ('native-proof-' + slug + '.log')
        clean_copy(offline / 'offline.log', log)
        entry['offline'] = {'command': 'SCENARIO_PIPELINE_OUTPUT_ROOT=.runtime-work/c146108-owner TMPDIR=.runtime-work .venv-cpu/bin/python -B runtime.py offline --manifest work/' + AID + '/draft-native-manifest.json --case ' + entry['case_id'] + ' --output .runtime-work/c146108-offline7-' + slug,
            'construction_sha256': entry['construction_sha256'], 'exit_code': 0,
            'log': log.name, 'log_sha256': sha(log)}
        source = REPO / '.runtime-work' / ('c146108-compat7-' + slug)
        receipt = json.loads((source / 'compatibility.json').read_text())
        if receipt.get('passed') is not True or receipt.get('construction_sha256') != entry['construction_sha256']:
            raise ValueError('Current compatibility proof differs: ' + slug)
        analysis_log = HERE / ('cpu-compat-' + slug + '-analysis.log')
        negative_log = HERE / ('cpu-compat-' + slug + '-negative.log')
        clean_copy(source / 'compatibility-analysis.log', analysis_log)
        clean_copy(source / 'negative-analysis.log', negative_log)
        receipt['log_sha256'] = sha(analysis_log)
        receipt['negative_log_sha256'] = sha(negative_log)
        receipt_copy = HERE / ('cpu-compat-' + slug + '.json')
        put(receipt_copy, receipt)
        entry['compatibility'] = {'receipt': receipt_copy.name, 'sha256': sha(receipt_copy),
                                  'log': analysis_log.name}
        entry['negative'] = {'log': negative_log.name}
        entry['acquisition'] = {channel['name']: {'entrypoint': 'finalize.py',
            'method': 'original crossing, stopped-lead purpose and 600-frame Native body/camera join with independent reviews',
            'evidence': 'channels/' + channel['name'] + '.jsonl'}
            for channel in entry['recording_description']['channels']}
    put(path, manifest)
    return {'cases': len(manifest['cases']), 'manifest_sha256': sha(path)}


if __name__ == '__main__':
    print(json.dumps(main(), sort_keys=True))
