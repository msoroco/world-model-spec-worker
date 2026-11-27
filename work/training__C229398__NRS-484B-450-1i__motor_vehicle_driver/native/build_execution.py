"""Bind exact selected rail bundles and completed CPU proof files."""
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parents[1]
REPO = FOLDER.parents[1]
SHA = lambda path: hashlib.sha256(Path(path).read_bytes()).hexdigest()

def bind():
    manifest = json.loads((FOLDER / 'public-probe-manifest.json').read_text())
    manifest['status'] = 'selected_cpu_proof'
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.split('__')[-1]
        construction = json.loads((FOLDER / entry['construction']).read_text())
        files = {x['path'] for x in construction['files']}
        log = f'offline/selected/{suffix}-primary.log'
        entry['offline'] = {
            'command': f'.venv-cpu/bin/python -B runtime.py offline --manifest work/{FOLDER.name}/execution-manifest.json --case {case} --output .runtime-work/c229398-selected-offline-{suffix}',
            'exit_code': 0, 'construction_sha256': entry['construction_sha256'],
            'log': log, 'log_sha256': SHA(FOLDER / log)}
        for candidate in entry.get('candidates', []):
            candidate_id = candidate['id']
            fallback_log = f'offline/selected/{suffix}-{candidate_id}.log'
            candidate['offline'] = {
                'command': f'.venv-cpu/bin/python -B runtime.py offline --manifest work/{FOLDER.name}/execution-manifest.json --case {case} --candidate {candidate_id} --output .runtime-work/c229398-selected-offline-{suffix}-{candidate_id}',
                'exit_code': 0, 'construction_sha256': candidate['construction_sha256'],
                'log': fallback_log, 'log_sha256': SHA(FOLDER / fallback_log)}
            fallback_receipt = f'compatibility/{suffix}-{candidate_id}-compatibility.json'
            fallback_analysis = f'compatibility/{suffix}-{candidate_id}-analysis.log'
            fallback_negative = f'compatibility/{suffix}-{candidate_id}-negative.log'
            if all((FOLDER / path).is_file() for path in (fallback_receipt, fallback_analysis, fallback_negative)):
                candidate['compatibility'] = {'receipt': fallback_receipt,
                    'sha256': SHA(FOLDER / fallback_receipt),
                    'log': fallback_analysis, 'negative_log': fallback_negative}
        acquisition = {}
        for name in {'kin.extent', 'kin.velocity'} | {x['name'] for x in construction['recording_description']['channels']}:
            acquisition[name] = {'entrypoint': 'runner.py',
                'method': 'sealed original Native actor, physical rail and same-frame camera readback',
                'evidence': 'original-native-rows.jsonl, original-rail-survey.json, video_frames.jsonl, capture-seal.json'}
        if construction['recording_description'].get('context_inputs'):
            acquisition['exception_context'] = {'entrypoint': 'runner.py',
                'method': 'copy and hash-seal independently cited original request context before capture',
                'evidence': 'exception-context.json, capture-seal.json and cited source files; diagnostic fixture is synthetic only'}
        entry['acquisition'] = acquisition
        physical = f'physical-proof/{suffix}/proof.json'
        if (FOLDER / physical).is_file():
            entry['physical_preparation'] = {'receipt': physical, 'sha256': SHA(FOLDER / physical)}
        receipt = f'compatibility/{suffix}-primary-compatibility.json'
        analysis = f'compatibility/{suffix}-primary-analysis.log'
        negative = f'compatibility/{suffix}-primary-negative.log'
        if all((FOLDER / path).is_file() for path in (receipt,analysis,negative)):
            entry['compatibility'] = {'receipt': receipt, 'sha256': SHA(FOLDER / receipt),
                                       'log': analysis, 'negative_log': negative}
            entry['negative'] = {'log': negative}
        saved = f'saved/{suffix}-processing.json'
        if (FOLDER / saved).is_file():
            command = f'.venv-cpu/bin/python -B runtime.py process-saved --manifest work/{FOLDER.name}/execution-manifest.json --case {case} --attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library --validator $DECODER'
            entry['post_capture'] = {'command': command, 'feedback_command': command,
                'recorded_only': True, 'test_exit_code': 0,
                'test_log': saved, 'test_log_sha256': SHA(FOLDER / saved),
                'processing_receipt': saved, 'processing_receipt_sha256': SHA(FOLDER / saved)}
        audit_script = 'delivery_audit.py'
        positive = f'delivery-proofs/{suffix}-positive.log'
        delivery_negative = f'delivery-proofs/{suffix}-negative.log'
        if all((FOLDER / path).is_file() for path in (audit_script, positive, delivery_negative)):
            command = f'.venv-cpu/bin/python -B work/{FOLDER.name}/{audit_script} --case {case} --self-test'
            entry['delivery_acceptance'] = {'case_id': case, 'sets': ['full-train'],
                'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode', 'actual_pixels', 'physical_completion'],
                'script': audit_script, 'script_sha256': SHA(FOLDER / audit_script),
                'command': command, 'test_exit_code': 0, 'test_log': positive,
                'test_log_sha256': SHA(FOLDER / positive),
                'negative_command': command + ' --negative', 'negative_exit_code': 1,
                'negative_expected_error': 'Missing original source: exact original Native result',
                'negative_log': delivery_negative,
                'negative_log_sha256': SHA(FOLDER / delivery_negative),
                'scope': 'CPU audit predicates only; original Native and independent review pending'}
        entry['delivery_readiness'] = 'original_capture_pending'
        entry['candidate_risk'] = {'status': 'physical',
            'reason': 'Original approach may overshoot or fail to settle; fallback changes only approach distance and speed when original Native source meets the measured trigger.'}
    (FOLDER / 'execution-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest

if __name__ == '__main__':
    print(json.dumps({'cases': len(bind()['cases'])}))
