"""Bind source-independent positive and synthetic-source rejection audit tests."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CHECKS = ['native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    path = HERE / 'draft-native-manifest.json'
    manifest = json.loads(path.read_text())
    script = 'delivery_audit.py'
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.rsplit('__', 1)[-1]
        positive = 'delivery-' + suffix + '-positive.log'
        negative = 'delivery-' + suffix + '-negative.log'
        if 'cpu_predicates_passed' not in (HERE / positive).read_text():
            raise ValueError('Positive audit predicate missing: ' + suffix)
        if 'Exact original Native result missing' not in (HERE / negative).read_text():
            raise ValueError('Negative audit predicate missing: ' + suffix)
        entry['delivery_acceptance'] = {'case_id': case, 'sets': ['full-train'],
            'checks': CHECKS, 'script': script, 'script_sha256': sha(HERE / script),
            'command': '.venv-cpu/bin/python -B work/' + HERE.name + '/' + script + ' --case ' + case + ' --self-test',
            'test_exit_code': 0, 'test_log': positive, 'test_log_sha256': sha(HERE / positive),
            'negative_command': '.venv-cpu/bin/python -B work/' + HERE.name + '/' + script + ' --case ' + case + ' --self-test --negative',
            'negative_exit_code': 1, 'negative_expected_error': 'Exact original Native result missing',
            'negative_log': negative, 'negative_log_sha256': sha(HERE / negative),
            'diagnostic_scope': 'CPU predicates only; original Native pixels, area class, continuity, physical completion and legal judgment pending',
            'production_command': 'PYTHONPATH=runtime/scenario_pipeline .venv-cpu/bin/python -B work/' + HERE.name + '/' + script +
                ' --case ' + case + ' --attempt $ATTEMPT --review original-review.json --video raw.mkv --trace trace.jsonl'
                ' --job $JOB_ID --recording-id $RECORDING_ID --output $AUDIT_OUTPUT'}
    path.write_text(json.dumps(manifest, indent=2, allow_nan=False) + '\n')
    print(json.dumps({'cases': len(manifest['cases']), 'manifest_sha256': sha(path)}, sort_keys=True))


if __name__ == '__main__':
    main()
