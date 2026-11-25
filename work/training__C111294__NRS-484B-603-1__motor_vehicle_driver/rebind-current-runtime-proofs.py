"""Bind only verified current-runtime selected proof artifacts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(relative):
    return hashlib.sha256((HERE / relative).read_bytes()).hexdigest()


def proof_paths(suffix, candidate):
    if suffix.startswith('probe_'):
        stem = 'current-v2-' + suffix + ('' if candidate == 'primary' else '-fallback1')
        offline = 'current-v2-' + suffix + '-' + candidate + '-offline.log'
        return offline, stem + '-compatibility.json', stem + '-positive.log', stem + '-negative.log'
    branch = suffix.split('_probe_')[0]
    stem = suffix if candidate == 'primary' else suffix + '-fallback1'
    base = branch + '-branch-drafts/' + stem + '/'
    return base + 'offline.log', base + 'compatibility.json', base + 'analysis.log', base + 'negative.log'


def exact_offline_command(suffix, candidate):
    if suffix.startswith('probe_'):
        manifest = 'current-v2-' + suffix + ('' if candidate == 'primary' else '-fallback1') + '-diagnostic-manifest.json'
    else:
        manifest = suffix + '-diagnostic-manifest.json'
    return ('.venv-cpu/bin/python runtime.py offline --manifest work/' + HERE.name + '/' + manifest +
            ' --case ' + HERE.name + '__' + suffix + ' --candidate ' + candidate +
            ' --output .runtime-work/c111294-' + suffix + '-' + candidate +
            '-offline-v6 --python "$PWD/.venv-cpu/bin/python"')


def bind(entry, suffix, candidate, item):
    construction = item['construction']
    item['construction_sha256'] = sha(construction)
    offline_log, receipt_path, analysis_log, negative_log = proof_paths(suffix, candidate)
    receipt = json.loads((HERE / receipt_path).read_text())
    if (receipt.get('passed') is not True or receipt.get('case_id') != HERE.name + '__' + suffix or
            receipt.get('candidate_id') != candidate or receipt.get('construction_sha256') != item['construction_sha256'] or
            receipt.get('log_sha256') != sha(analysis_log) or receipt.get('negative_log_sha256') != sha(negative_log)):
        raise ValueError('Public proof is stale: ' + suffix + '/' + candidate)
    item['offline'] = {'case_id': HERE.name + '__' + suffix,
                       'candidate_id': candidate,
                       'construction_sha256': item['construction_sha256'],
                       'command': exact_offline_command(suffix, candidate),
                       'exit_code': 0, 'log': offline_log,
                       'log_sha256': sha(offline_log)}
    item['compatibility'] = {'receipt': receipt_path, 'sha256': sha(receipt_path),
                             'log': analysis_log, 'negative_log': negative_log}
    if candidate == 'primary':
        entry['negative'] = {'log': negative_log}


def main():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    if len(manifest['cases']) != 8:
        raise ValueError('Eight selected case entries required before rebinding')
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        bind(entry, suffix, 'primary', entry)
        for candidate in entry['candidates']:
            bind(entry, suffix, candidate['id'], candidate)
        physical = entry['physical_preparation']['receipt']
        entry['physical_preparation']['sha256'] = sha(physical)
        post = entry['post_capture']
        post['test_log_sha256'] = sha(post['test_log'])
        post['processing_sha256'] = sha(post['processing_receipt'])
        acceptance = entry['delivery_acceptance']
        acceptance['script_sha256'] = sha(acceptance['script'])
        acceptance['test_log_sha256'] = sha(acceptance['test_log'])
        acceptance['negative_log_sha256'] = sha(acceptance['negative_log'])
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'selected_cases': len(manifest['cases']), 'manifest_sha256': sha('execution-manifest.json')}))


if __name__ == '__main__':
    main()
