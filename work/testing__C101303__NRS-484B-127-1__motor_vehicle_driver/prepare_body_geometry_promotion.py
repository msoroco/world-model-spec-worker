"""Assemble a reviewable manifest with exact draft proof receipts."""
import hashlib
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
DRAFT = ROOT / 'body-geometry-all-draft-manifest.json'
PROOFS = ROOT / 'body-geometry-draft'
DEST = PROOFS / 'selected-proofs'
VALIDATOR = REPO / '.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_summary(name):
    value = json.loads((PROOFS / name).read_text())
    if value['manifest_sha256'] != digest(DRAFT) or value['passed_count'] != 32:
        raise ValueError('Draft proof summary is stale or incomplete: ' + name)
    return {(row['case_id'], row['candidate_id']): row for row in value['proofs']}


def main():
    baseline = (PROOFS / 'pre-promotion-execution-manifest.json'
                if (PROOFS / 'pre-promotion-execution-manifest.json').exists()
                else ROOT / 'execution-manifest.json')
    equivalence = json.loads((PROOFS / 'equivalence-proof.json').read_text())
    if (equivalence['selected_manifest_sha256'] != digest(baseline)
            or equivalence['draft_manifest_sha256'] != digest(DRAFT)
            or equivalence['bundle_count'] != 32):
        raise ValueError('Selected/draft equivalence proof changed')
    manifest = json.loads(DRAFT.read_text())
    offline = read_summary('all-offline-proof.json')
    compatibility = read_summary('all-compatibility-proof.json')
    saved = read_summary('all-saved-proof.json')
    if any(len(indexed) != 32 for indexed in (offline, compatibility, saved)):
        raise ValueError('Expected one proof per exact primary/fallback')
    DEST.mkdir(parents=True, exist_ok=True)
    for case in manifest['cases']:
        label = case['case_id'].rsplit('source_verified_', 1)[1]
        physical = PROOFS / 'physical-proofs' / label / 'receipt.json'
        receipt = json.loads(physical.read_text())
        if receipt['construction_sha256'] != case['construction_sha256']:
            raise ValueError('Draft physical proof selects another construction')
        case['physical_preparation'] = {'receipt': str(physical.relative_to(ROOT)),
                                        'sha256': digest(physical)}
        for row in [case] + case['candidates']:
            candidate_id = row.get('id', 'primary')
            key = (case['case_id'], candidate_id)
            one, two, three = offline[key], compatibility[key], saved[key]
            if any(proof['construction_sha256'] != row['construction_sha256']
                   for proof in (one, two, three)):
                raise ValueError('Proof construction hash differs: ' + str(key))
            suffix = 'source_verified_' + label + '-' + candidate_id
            proof_dir = DEST / suffix
            proof_dir.mkdir(exist_ok=True)
            compatibility_attempt = REPO / '.runtime-work/c101303-body-geometry-all-compat-v1' / suffix
            saved_attempt = REPO / '.runtime-work/c101303-body-geometry-all-saved-v1' / suffix
            for source_name, target_name in (
                    ('compatibility.json', 'compatibility.json'),
                    ('compatibility-analysis.log', 'analysis.log'),
                    ('negative-analysis.log', 'negative.log')):
                shutil.copyfile(compatibility_attempt / source_name,
                                proof_dir / target_name)
            shutil.copyfile(saved_attempt / 'v0001/processing.json',
                            proof_dir / 'saved-processing.json')
            compat_receipt = json.loads((proof_dir / 'compatibility.json').read_text())
            if (compat_receipt['case_id'] != case['case_id']
                    or compat_receipt['candidate_id'] != candidate_id
                    or compat_receipt['construction_sha256'] != row['construction_sha256']
                    or digest(proof_dir / 'analysis.log') != compat_receipt['log_sha256']
                    or digest(proof_dir / 'negative.log') != compat_receipt['negative_log_sha256']):
                raise ValueError('Compatibility receipt not source bound: ' + str(key))
            processing = json.loads((proof_dir / 'saved-processing.json').read_text())
            if (processing.get('passed') is not True
                    or processing['analysis_revision']['construction_sha256']
                    != row['construction_sha256']
                    or processing.get('recorded_only') is not True
                    or processing.get('originals_preserved') is not True):
                raise ValueError('Saved receipt not construction bound: ' + str(key))
            offline_log = ROOT / one['log']
            compatibility_log = ROOT / two['log']
            saved_log = ROOT / three['log']
            if any(digest(ROOT / proof['log']) != proof['log_sha256']
                   for proof in (one, two, three)):
                raise ValueError('Draft proof log changed: ' + str(key))
            offline_command = [str(REPO / '.venv-cpu/bin/python'), str(REPO / 'runtime.py'),
                               'offline', '--manifest', str(DRAFT), '--case', case['case_id'],
                               '--output', str(REPO / '.runtime-work/c101303-body-geometry-all-draft-v2' / suffix)]
            compatibility_command = [str(REPO / '.venv-cpu/bin/python'), str(REPO / 'runtime.py'),
                                     'compatibility', '--manifest', str(DRAFT), '--case', case['case_id'],
                                     '--candidate', candidate_id, '--output', str(compatibility_attempt),
                                     '--library', str(REPO / 'runtime/library'), '--validator', str(VALIDATOR)]
            saved_command = [str(REPO / '.venv-cpu/bin/python'), str(REPO / 'runtime.py'),
                             'process-saved', '--manifest', str(DRAFT), '--case', case['case_id'],
                             '--attempt', str(compatibility_attempt), '--output', str(saved_attempt),
                             '--library', str(REPO / 'runtime/library'), '--validator', str(VALIDATOR)]
            if candidate_id != 'primary':
                offline_command.extend(['--candidate', candidate_id])
            row['offline'] = {'command': ' '.join(offline_command), 'exit_code': 0,
                              'log': str(offline_log.relative_to(ROOT)),
                              'log_sha256': digest(offline_log),
                              'construction_sha256': row['construction_sha256']}
            row['compatibility'] = {
                'receipt': str((proof_dir / 'compatibility.json').relative_to(ROOT)),
                'sha256': digest(proof_dir / 'compatibility.json'),
                'log': str((proof_dir / 'analysis.log').relative_to(ROOT)),
                'negative_log': str((proof_dir / 'negative.log').relative_to(ROOT)),
                'replay_command': ' '.join(compatibility_command),
                'replay_log': str(compatibility_log.relative_to(ROOT)),
                'replay_log_sha256': digest(compatibility_log)}
            row['post_capture'] = {
                'recorded_only': True, 'command': ' '.join(saved_command),
                'test_log': str(saved_log.relative_to(ROOT)),
                'test_log_sha256': digest(saved_log), 'test_exit_code': 0,
                'processing_receipt': str((proof_dir / 'saved-processing.json').relative_to(ROOT)),
                'processing_sha256': digest(proof_dir / 'saved-processing.json')}
            if candidate_id == 'primary':
                row['negative'] = {'log': row['compatibility']['negative_log']}
                row['post_capture']['feedback_command'] = 'cat ' + str(
                    saved_attempt / 'v0001/feedback.json')
        print('assembled', label, 'primary and three fallbacks', flush=True)
    target = PROOFS / 'promotion-candidate.json'
    target.write_text(json.dumps(manifest, indent=2) + '\n')
    print('promotion candidate', digest(target))


if __name__ == '__main__':
    main()
