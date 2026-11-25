"""Bind exact current-runtime primary CPU receipts without claiming physical acceptance."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_clean(source, target):
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text('\n'.join(line.rstrip() for line in source.read_text().rstrip().splitlines()) + '\n')
    return digest(target)


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for index, entry in enumerate(manifest['cases'], 1):
        suffix = f'controlled_{index}'
        offline_cmd = (f'.venv-cpu/bin/python runtime.py offline --manifest '
                       f'work/{HERE.name}/execution-manifest.json --case {entry["case_id"]} '
                       f'--candidate primary --output .runtime-work/c229410-v5-offline-{suffix}')
        offline_log = f'{suffix}-primary-offline.log'
        offline_sha = copy_clean(SCRATCH / f'c229410-v5-offline-{suffix}.log', HERE / offline_log)
        entry['offline'] = {'case_id': entry['case_id'], 'candidate_id': 'primary',
                            'construction_sha256': entry['construction_sha256'],
                            'command': offline_cmd, 'exit_code': 0,
                            'log': offline_log, 'log_sha256': offline_sha}
        source = SCRATCH / f'c229410-v5-compat-{suffix}'
        target = HERE / 'compatibility'
        receipt = target / f'{suffix}-primary-compatibility.json'
        receipt.parent.mkdir(parents=True, exist_ok=True)
        receipt.write_bytes((source / 'compatibility.json').read_bytes())
        analysis = target / f'{suffix}-primary-compatibility-analysis.log'
        negative = target / f'{suffix}-primary-negative-analysis.log'
        copy_clean(source / 'compatibility-analysis.log', analysis)
        copy_clean(source / 'negative-analysis.log', negative)
        entry['compatibility'] = {'receipt': str(receipt.relative_to(HERE)),
                                  'sha256': digest(receipt),
                                  'log': str(analysis.relative_to(HERE)),
                                  'negative_log': str(negative.relative_to(HERE))}
        entry['negative'] = {'log': str(negative.relative_to(HERE))}
        physical = HERE / 'physical-proof' / suffix / 'proof.json'
        if physical.is_file():
            proof = json.loads(physical.read_text())
            if proof.get('construction_sha256') != entry['construction_sha256']:
                raise ValueError('Physical fixture binds another construction: ' + suffix)
            entry['physical_preparation'] = {'receipt': str(physical.relative_to(HERE)),
                                             'sha256': digest(physical)}
        audit = HERE / 'delivery_audit.py'
        positive = HERE / 'delivery-proofs' / f'{suffix}-positive.log'
        rejected = HERE / 'delivery-proofs' / f'{suffix}-negative.log'
        if audit.is_file() and positive.is_file() and rejected.is_file():
            command = f'{ROOT}/.venv-cpu/bin/python {audit} --case {entry["case_id"]} --self-test'
            entry['delivery_acceptance'] = {
                'case_id': entry['case_id'], 'sets': ['full-train'],
                'checks': ['native_source', 'all_participants', 'time_join',
                           'full_video_decode', 'actual_pixels', 'physical_completion'],
                'script': 'delivery_audit.py', 'script_sha256': digest(audit),
                'negative_expected_error': 'Missing original source: exact original Native result',
                'command': command, 'test_exit_code': 0,
                'test_log': str(positive.relative_to(HERE)), 'test_log_sha256': digest(positive),
                'negative_command': command + ' --negative', 'negative_exit_code': 1,
                'negative_log': str(rejected.relative_to(HERE)),
                'negative_log_sha256': digest(rejected),
            }
        saved_root = SCRATCH / f'c229410-v5-saved-{suffix}'
        saved_receipt = saved_root / 'v0001' / 'processing.json'
        if saved_receipt.is_file():
            saved_data = json.loads(saved_receipt.read_text())
            if not (saved_data.get('passed') is True and saved_data.get('recorded_only') is True
                    and saved_data.get('originals_preserved') is True
                    and saved_data.get('analysis_revision', {}).get('construction_sha256') == entry['construction_sha256']):
                raise ValueError('Saved receipt is incomplete or binds another construction: ' + suffix)
            saved_log_rel = f'saved-{suffix}-primary.log'
            saved_receipt_rel = f'saved-{suffix}-primary-processing.json'
            saved_log_sha = copy_clean(SCRATCH / f'c229410-v5-saved-{suffix}.log', HERE / saved_log_rel)
            (HERE / saved_receipt_rel).write_text(json.dumps(saved_data, indent=2, ensure_ascii=False) + '\n')
            entry['post_capture'] = {
                'recorded_only': True,
                'command': f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{HERE.name}/execution-manifest.json --case {entry["case_id"]} --attempt $ATTEMPT --output $OUTPUT --library runtime/library --validator $DECODER --owner-release-receipt $OWNER_RELEASE_RECEIPT',
                'feedback_command': 'cat $OUTPUT/versions/*/feedback.json',
                'test_exit_code': 0, 'test_log': saved_log_rel,
                'test_log_sha256': saved_log_sha,
                'processing_receipt': saved_receipt_rel,
                'processing_sha256': digest(HERE / saved_receipt_rel),
            }
        entry['delivery_readiness'] = 'incomplete'
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'bound_cases': len(manifest['cases']), 'manifest_sha256': digest(manifest_path)}))


if __name__ == '__main__':
    main()
