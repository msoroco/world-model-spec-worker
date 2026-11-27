"""Bind exact offline and public positive/negative alternative receipts."""
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
        candidate = entry['candidates'][0]
        source = REPO / '.runtime-work' / ('c245490_fallback_offline_v1_' + suffix) / 'offline.log'
        if 'OK' not in source.read_text():
            raise ValueError('Fallback offline proof missing: ' + suffix)
        offline = HERE / ('fallback-' + suffix + '-offline.log')
        offline.write_text(source.read_text().rstrip() + '\n')
        candidate['offline'] = {'command': '.venv-cpu/bin/python -B runtime.py offline --manifest '
            + 'work/' + HERE.name + '/execution-manifest.json --case ' + entry['case_id']
            + ' --candidate fallback1 --output $OFFLINE_OUTPUT --python $CARLA_PYTHON',
            'construction_sha256': candidate['construction_sha256'], 'exit_code': 0,
            'log': offline.name, 'log_sha256': sha(offline)}
        proof_source = REPO / '.runtime-work' / ('c245490_fallback_compat_v1_' + suffix)
        proof = json.loads((proof_source / 'compatibility.json').read_text())
        if (proof.get('passed') is not True or proof.get('candidate_id') != 'fallback1'
                or proof.get('construction_sha256') != candidate['construction_sha256']):
            raise ValueError('Fallback public proof stale: ' + suffix)
        for original, target in (('compatibility-analysis.log', 'fallback-' + suffix + '-analysis.log'),
                                 ('negative-analysis.log', 'fallback-' + suffix + '-negative.log')):
            (HERE / target).write_text((proof_source / original).read_text().rstrip() + '\n')
        proof['log_sha256'] = sha(HERE / ('fallback-' + suffix + '-analysis.log'))
        proof['negative_log_sha256'] = sha(HERE / ('fallback-' + suffix + '-negative.log'))
        receipt = HERE / ('fallback-' + suffix + '.json')
        receipt.write_text(json.dumps(proof, indent=2, allow_nan=False) + '\n')
        candidate['compatibility'] = {'receipt': receipt.name, 'sha256': sha(receipt),
            'log': 'fallback-' + suffix + '-analysis.log',
            'negative_log': 'fallback-' + suffix + '-negative.log'}
    path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'cases': len(manifest['cases']), 'manifest_sha256': sha(path)}, sort_keys=True))


if __name__ == '__main__':
    main()
