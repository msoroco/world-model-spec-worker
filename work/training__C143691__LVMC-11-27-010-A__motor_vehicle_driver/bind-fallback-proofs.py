"""Bind seven exact fallback offline and public compatibility receipts."""
import hashlib
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def copy(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    return sha(target)


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.rsplit('__', 1)[-1]
        candidate = entry['candidates'][0]
        if candidate['id'] != 'fallback1' or entry['candidate_risk']['status'] != 'physical':
            raise ValueError('Expected one physical barrier fallback')
        original = json.loads((HERE / entry['construction']).read_text())
        alternative = json.loads((HERE / candidate['construction']).read_text())
        primary_config = json.loads(next(item['content'] for item in original['files']
                                         if item['path'] == 'config.json'))
        fallback_config = json.loads(next(item['content'] for item in alternative['files']
                                          if item['path'] == 'config.json'))
        if any(primary_config[key] != fallback_config[key] for key in
               ('law_id', 'cell_id', 'actor', 'case_id', 'selected_case_id',
                'source_context_request', 'route_case', 'rate_hz', 'duration_s',
                'cameras', 'recording_description')):
            raise ValueError('Fallback changed fixed comparison or source conditions')
        version = 'v2' if suffix == 'no_designation' else 'v1'
        proof = ROOT / '.runtime-work' / ('c143691-fallback-compat-' + suffix + '-' + version)
        receipt = json.loads((proof / 'compatibility.json').read_text())
        if (receipt.get('passed') is not True or receipt.get('case_id') != case
                or receipt.get('candidate_id') != 'fallback1'
                or receipt.get('construction_sha256') != candidate['construction_sha256']):
            raise ValueError('Fallback public compatibility differs: ' + suffix)
        offline_log = HERE / 'offline' / (suffix + '-fallback1.log')
        if not offline_log.is_file() or 'offline' not in offline_log.read_text():
            raise ValueError('Fallback exact offline log missing: ' + suffix)
        receipt_path = HERE / 'compatibility' / (suffix + '-fallback1.json')
        analysis_log = HERE / 'compatibility' / (suffix + '-fallback1-analysis.log')
        negative_log = HERE / 'compatibility' / (suffix + '-fallback1-negative.log')
        copy(proof / 'compatibility.json', receipt_path)
        copy(proof / 'compatibility-analysis.log', analysis_log)
        copy(proof / 'negative-analysis.log', negative_log)
        if (sha(analysis_log) != receipt['log_sha256']
                or sha(negative_log) != receipt['negative_log_sha256']):
            raise ValueError('Fallback public logs differ: ' + suffix)
        candidate['offline'] = {
            'command': '.venv-cpu/bin/python -B runtime.py offline --manifest work/'
                       + HERE.name + '/execution-manifest.json --case ' + case
                       + ' --candidate fallback1 --output .runtime-work/c143691-fallback-offline-'
                       + suffix + '-v1',
            'exit_code': 0,
            'construction_sha256': candidate['construction_sha256'],
            'log': str(offline_log.relative_to(HERE)),
            'log_sha256': sha(offline_log),
        }
        candidate['compatibility'] = {
            'receipt': str(receipt_path.relative_to(HERE)),
            'sha256': sha(receipt_path),
            'log': str(analysis_log.relative_to(HERE)),
            'negative_log': str(negative_log.relative_to(HERE)),
        }
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'fallbacks_bound': len(manifest['cases']),
                      'manifest_sha256': sha(MANIFEST)}))


if __name__ == '__main__':
    main()
