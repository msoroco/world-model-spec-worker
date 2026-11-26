"""Bind completed exact-case CPU receipts without altering selected constructions."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
REPO = FOLDER.parents[1]
MANIFEST = FOLDER / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind():
    manifest = json.loads(MANIFEST.read_text())
    assignment = FOLDER.name
    script = 'delivery_audit.py'
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.removeprefix(assignment + '__')
        offline = f'offline/selected/{suffix}.log'
        physical = f'physical-proof/{suffix}/proof.json'
        receipt = f'compatibility/{suffix}-primary-compatibility.json'
        analysis = f'compatibility/{suffix}-primary-analysis.log'
        negative = f'compatibility/{suffix}-primary-negative.log'
        saved = f'saved/{suffix}-processing.json'
        saved_log = f'saved/{suffix}-processing.log'
        positive = f'delivery-proofs/{suffix}-positive.log'
        delivery_negative = f'delivery-proofs/{suffix}-negative.log'
        paths = (offline, physical, receipt, analysis, negative, saved,
                 saved_log, positive, delivery_negative)
        if any(not (FOLDER / p).is_file() for p in paths):
            raise ValueError('Missing exact-case proof for ' + suffix)
        proof = json.loads((FOLDER / receipt).read_text())
        saved_proof = json.loads((FOLDER / saved).read_text())
        if (not proof['passed'] or not saved_proof['passed'] or
                saved_proof['analysis_revision']['construction_sha256'] != entry['construction_sha256']):
            raise ValueError('Selected proof failed or changed: ' + suffix)
        entry['offline'] = {'command': '.venv-cpu/bin/python -B runtime.py offline '
            f'--manifest work/{assignment}/execution-manifest.json --case {case} '
            f'--output .runtime-work/owner229397/selected-offline-v3-{suffix}',
            'exit_code': 0, 'construction_sha256': entry['construction_sha256'],
            'log': offline, 'log_sha256': sha(FOLDER / offline)}
        entry['physical_preparation'] = {'receipt': physical,
            'sha256': sha(FOLDER / physical)}
        entry['compatibility'] = {'receipt': receipt,
            'sha256': sha(FOLDER / receipt), 'log': analysis,
            'negative_log': negative}
        entry['negative'] = {'log': negative}
        saved_cmd = f'.venv-cpu/bin/python -B runtime.py process-saved --manifest work/{assignment}/execution-manifest.json --case {case} --attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library --validator $DECODER'
        entry['post_capture'] = {'command': saved_cmd,
            'feedback_command': saved_cmd, 'recorded_only': True,
            'test_exit_code': 0, 'test_log': saved_log,
            'test_log_sha256': sha(FOLDER / saved_log),
            'processing_receipt': saved, 'processing_receipt_sha256': sha(FOLDER / saved)}
        pos_cmd = f'.venv-cpu/bin/python -B work/{assignment}/{script} --case {case} --self-test'
        neg_cmd = pos_cmd + ' --negative'
        entry['delivery_acceptance'] = {'case_id': case,
            'sets': ['demo-train', 'full-train'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'script': script, 'script_sha256': sha(FOLDER / script),
            'command': pos_cmd, 'test_exit_code': 0, 'test_log': positive,
            'test_log_sha256': sha(FOLDER / positive),
            'negative_command': neg_cmd, 'negative_exit_code': 1,
            'negative_expected_error': 'Missing original source: exact original Native result',
            'negative_log': delivery_negative,
            'negative_log_sha256': sha(FOLDER / delivery_negative),
            'scope': 'CPU predicates only; original Native capture is pending'}
        # No concrete failed physical trigger has been observed in original Native.
        entry['candidate_risk'] = {'status': 'none',
            'reason': 'No measured original Native physical failure trigger yet; retain this selected construction for first capture and assess fallback only from recorded feedback'}
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    bind()
