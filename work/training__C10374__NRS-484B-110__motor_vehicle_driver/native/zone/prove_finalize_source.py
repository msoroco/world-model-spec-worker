"""CPU proof for two retained saved conditions and missing/altered source."""
import argparse
import hashlib
import json
import shutil
import tempfile
from pathlib import Path

from finalize_source import finalize


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--assignment', required=True)
    parser.add_argument('--runtime-work', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    assignment = Path(args.assignment)
    work = Path(args.runtime_work)
    results = []
    for condition, suffix, expected in (
        ('a', 'condition_a', 60), ('b', 'condition_b', 0)):
        bundle = assignment / 'native/zone/offline/bundles' / ('selected_c5852cfd__' + suffix) / 'primary'
        saved = work / ('c10374-current-saved-' + condition)
        raw = work / ('c10374-current-graph-' + condition)
        result = finalize(bundle, saved, raw)
        assert result['target_check']['measured'] == expected
        assert result['source_kind'] == 'synthetic_cpu'
        assert not result['physical_acceptance_claimed']
        assert result['source_bindings']['raw_source_reverified']
        results.append({'condition': suffix, 'overlap_frames': expected,
                        'receipt_sha256': result['source_bindings']['preparation_receipt_sha256']})
    bundle = assignment / 'native/zone/offline/bundles/selected_c5852cfd__condition_a/primary'
    with tempfile.TemporaryDirectory(dir=work) as temp:
        copy = Path(temp) / 'saved'
        shutil.copytree(work / 'c10374-current-saved-a', copy)
        rows = copy / 'native-observed.jsonl'
        original = rows.read_bytes()
        rows.write_bytes(original.replace(b'"frame": 0,', b'"frame": 1,', 1))
        try:
            finalize(bundle, copy)
        except ValueError as exc:
            assert 'prepared source and joins' in str(exc)
        else:
            raise AssertionError('altered saved source accepted')
        rows.write_bytes(original)
        (copy / 'frame-review.jsonl').unlink()
        try:
            finalize(bundle, copy)
        except FileNotFoundError:
            pass
        else:
            raise AssertionError('missing saved review accepted')
        raw = Path(temp) / 'raw'
        shutil.copytree(work / 'c10374-current-graph-a', raw)
        source = raw / 'native-raw-actors.jsonl'
        source.write_bytes(source.read_bytes() + b'\n')
        try:
            finalize(bundle, work / 'c10374-current-saved-a', raw)
        except ValueError as exc:
            assert 'retained raw source changed' in str(exc)
        else:
            raise AssertionError('altered raw source accepted')
    receipt = {
        'format': 'c10374-zone-source-finalization-proof-v1', 'passed': True,
        'finalizer_sha256': sha(Path(__file__).with_name('finalize_source.py')),
        'conditions': results, 'changed_saved_source_rejected': True,
        'missing_saved_source_rejected': True,
        'changed_raw_source_rejected': True,
        'physical_acceptance_claimed': False, 'legal_outcome_claimed': False,
    }
    Path(args.output).write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': True, 'overlap_frames': [60, 0],
                      'negative_cases': 3}))


if __name__ == '__main__':
    main()
