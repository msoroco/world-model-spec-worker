"""Bind recorded-only CPU fixture tests after all exact candidates have run."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CASES = ('probe_a', 'probe_b', 'curve_right', 'curve_left',
         'one_way_crest', 'one_way_curve')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def proof(candidate, suffix, selected):
    relative = 'saved-proofs/' + candidate + '-' + suffix
    log = HERE / (relative + '-test.log')
    receipt = HERE / (relative + '-processing.json')
    value = json.loads(log.read_text())
    result = json.loads(receipt.read_text())
    if (value.get('exit_code') != 0 or value.get('recorded_only') is not True
            or value.get('originals_preserved') is not True
            or value.get('native_replay_requested') is not False
            or value.get('processing_receipt_sha256') != sha(receipt)
            or value.get('analysis_revision_construction_sha256') != selected['construction_sha256']
            or result.get('passed') is not True or result.get('originals_preserved') is not True
            or result.get('candidate_id') != candidate):
        raise ValueError('Incomplete recorded-only proof: ' + candidate + ' ' + suffix)
    return {'test_command': '.venv-cpu/bin/python -B work/' + HERE.name +
                            '/run_saved.py --case ' + suffix + ' --candidate ' + candidate,
            'test_exit_code': 0, 'test_log': relative + '-test.log',
            'test_log_sha256': sha(log),
            'processing_receipt': relative + '-processing.json',
            'processing_receipt_sha256': sha(receipt),
            'originals_preserved': True, 'native_replay_requested': False}


def main():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    for suffix, entry in zip(CASES, manifest['cases']):
        if entry['case_id'] != HERE.name + '__' + suffix:
            raise ValueError('Exact case order differs')
        entry['post_capture'].update(proof('primary', suffix, entry))
        entry['candidates'][0]['post_capture_test'] = proof('fallback1', suffix,
                                                            entry['candidates'][0])
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'bound_case_count': len(manifest['cases']),
                      'execution_manifest_sha256': sha(path)}))


if __name__ == '__main__':
    main()
