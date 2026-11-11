"""Run current exact saved processing for every C136539 selected primary."""

from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import sys
from uuid import uuid4

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.json'
VALIDATOR = ROOT / '.runtime-work/c125714-validator/.lake/build/bin/adapterCheck'


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


manifest = json.loads(MANIFEST.read_text())
for entry in manifest['cases']:
    case = entry['case_id']; suffix = case.split('__')[-1]
    prefix = ROOT / '.runtime-work' / f'c136539-{suffix}-saved-sweep-{uuid4().hex[:8]}'
    fixture = Path(str(prefix) + '-fixture')
    attempt = Path(str(prefix) + '-attempt')
    output = Path(str(prefix) + '-output')
    subprocess.run([sys.executable, str(ROOT / 'runtime.py'), 'fixture',
                    '--recipe', str(ROOT / entry['fixture_recipe']), '--output', str(fixture)],
                   cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    subprocess.run([sys.executable, str(ROOT / 'runtime.py'), 'offline',
                    '--manifest', str(MANIFEST), '--case', case,
                    '--output', str(attempt), '--python', sys.executable],
                   cwd=ROOT, check=True, stdout=subprocess.DEVNULL)
    for path in fixture.rglob('*'):
        if path.is_file():
            target = attempt / path.relative_to(fixture)
            if target.exists():
                raise ValueError('Diagnostic source shadows construction: ' + str(target))
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
    command = [sys.executable, str(ROOT / 'runtime.py'), 'process-saved',
               '--manifest', str(MANIFEST), '--case', case, '--attempt', str(attempt),
               '--output', str(output), '--library', str(ROOT / 'runtime/library'),
               '--validator', str(VALIDATOR)]
    log_rel = f'cases/execution-saved-{suffix}.log'
    with (HERE / log_rel).open('w') as stream:
        subprocess.run(command, cwd=ROOT, check=True, stdout=stream, stderr=subprocess.STDOUT)
    source = output / 'v0001/processing.json'
    receipt = json.loads(source.read_text())
    if (not receipt['passed'] or not receipt['originals_preserved'] or
            not receipt['timestamp_joins']['passed'] or
            not receipt['final_video_checks']['passed'] or
            receipt['missing_evidence'] or
            receipt['native_revision']['construction_sha256'] != entry['construction_sha256']):
        raise ValueError('Saved processing proof incomplete: ' + suffix)
    shutil.copyfile(source, HERE / f'cases/execution-saved-{suffix}.json')
    audited_attempt = output / 'v0001/analysis'
    report_path = audited_attempt / 'analysis-report.json'
    audit_script = HERE / 'delivery_audit.py'
    positive = [sys.executable, str(audit_script), '--case', case,
                '--attempt', str(audited_attempt), '--report', str(report_path),
                '--diagnostic-fixture']
    stem = 'slow' if suffix == 'slow_person_exposure' else suffix
    positive_rel = f'delivery-audit-{stem}-positive.log'
    with (HERE / positive_rel).open('w') as stream:
        subprocess.run(positive, cwd=ROOT, check=True, stdout=stream, stderr=subprocess.STDOUT)
    tampered_path = Path(str(prefix) + '-tampered-report.json')
    tampered = json.loads(report_path.read_text())
    tampered['measurements']['person_or_property_exposure']['sources']['exposed_actor_footprints.jsonl'] = '0' * 64
    tampered_path.write_text(json.dumps(tampered, indent=2) + '\n')
    negative = [sys.executable, str(audit_script), '--case', case,
                '--attempt', str(audited_attempt), '--report', str(tampered_path),
                '--diagnostic-fixture']
    negative_rel = f'delivery-audit-{stem}-negative.log'
    with (HERE / negative_rel).open('w') as stream:
        check = subprocess.run(negative, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT)
    if check.returncode == 0 or 'Original exposure source hash differs from saved report' not in (HERE / negative_rel).read_text():
        raise ValueError('Tampered original-source audit was not rejected: ' + suffix)
    entry['post_capture'] = {
        'recorded_only': True,
        'command': f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{HERE.name}/execution-manifest.json --case {case} --attempt "$ATTEMPT" --output "$PROCESSING_OUTPUT" --library runtime/library --validator .runtime-work/c125714-validator/.lake/build/bin/adapterCheck',
        'feedback_command': 'cat "$PROCESSING_OUTPUT/feedback.json"',
        'test_log': log_rel, 'test_log_sha256': sha(HERE / log_rel), 'test_exit_code': 0}
    entry['delivery_acceptance'] = {
        'case_id': case, 'sets': ['held-out'],
        'checks': ['native_source', 'all_participants', 'time_join',
                   'full_video_decode', 'actual_pixels', 'physical_completion'],
        'script': 'delivery_audit.py', 'script_sha256': sha(audit_script),
        'command': ' '.join(positive), 'test_exit_code': 0,
        'test_log': positive_rel, 'test_log_sha256': sha(HERE / positive_rel),
        'negative_command': ' '.join(negative), 'negative_exit_code': check.returncode,
        'negative_expected_error': 'hash differs',
        'negative_log': negative_rel, 'negative_log_sha256': sha(HERE / negative_rel)}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')
    print(suffix, 'saved processing passed', flush=True)

index = {'format': 'worker-exposure-execution-saved-cpu-proofs',
         'scope': 'synthetic diagnostic saved processing through exact execution manifest; no Native physical claim',
         'manifest': 'execution-manifest.json',
         'manifest_sha256': sha(MANIFEST),
         'cases': [{'case_id': entry['case_id'],
                    'construction_sha256': entry['construction_sha256'],
                    'log': entry['post_capture']['test_log'],
                    'log_sha256': entry['post_capture']['test_log_sha256'],
                    'receipt': f'cases/execution-saved-{entry["case_id"].split("__")[-1]}.json',
                    'receipt_sha256': sha(HERE / f'cases/execution-saved-{entry["case_id"].split("__")[-1]}.json')}
                   for entry in manifest['cases']]}
(HERE / 'execution-saved-proofs.json').write_text(json.dumps(index, indent=2) + '\n')
audit_index = {'format': 'worker-exposure-delivery-audit-cpu-proofs',
               'scope': 'diagnostic software audit only; no Native physical or legal claim',
               'script': 'delivery_audit.py', 'script_sha256': sha(HERE / 'delivery_audit.py'),
               'cases': [{'case_id': e['case_id'],
                          'positive': {'log': e['delivery_acceptance']['test_log'],
                                       'sha256': e['delivery_acceptance']['test_log_sha256']},
                          'negative': {'log': e['delivery_acceptance']['negative_log'],
                                       'sha256': e['delivery_acceptance']['negative_log_sha256']}}
                         for e in manifest['cases']],
               'native_required_negative': json.loads((HERE / 'delivery-audit-proofs.json').read_text())['native_required_negative']}
(HERE / 'delivery-audit-proofs.json').write_text(json.dumps(audit_index, indent=2) + '\n')
primary_manifest = HERE / 'probe-compatibility-manifest.json'
primary = json.loads(primary_manifest.read_text())
primary_index = {'format': 'worker-exposure-primary-saved-cpu-proofs',
                 'assignment_id': HERE.name,
                 'scope': 'synthetic exact saved-processing software proof; no physical or legal acceptance',
                 'manifest': primary_manifest.name,
                 'manifest_sha256': sha(primary_manifest),
                 'cases': []}
for entry in primary['cases']:
    suffix = entry['case_id'].split('__')[-1]
    receipt_rel = f'cases/execution-saved-{suffix}.json'
    log_rel = f'cases/execution-saved-{suffix}.log'
    primary_index['cases'].append({
        'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
        'compatibility_receipt': entry['compatibility']['receipt'],
        'compatibility_sha256': entry['compatibility']['sha256'],
        'negative_log': entry['compatibility']['negative_log'],
        'negative_log_sha256': sha(HERE / entry['compatibility']['negative_log']),
        'saved_receipt': receipt_rel, 'saved_receipt_sha256': sha(HERE / receipt_rel),
        'saved_log': log_rel, 'saved_log_sha256': sha(HERE / log_rel),
        'saved_passed': True, 'originals_preserved': True, 'missing_evidence': False,
        'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False})
(HERE / 'primary-saved-proofs.json').write_text(json.dumps(primary_index, indent=2) + '\n')
