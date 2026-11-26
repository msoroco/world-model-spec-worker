"""Bind passing bicycle CPU receipts without asserting full statutory delivery."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind():
    draft = json.loads((HERE / 'draft-mounted-sidewalk-manifest.json').read_text())
    entries = []
    for number, source in enumerate(draft['cases'], 1):
        case = source['case_id']
        offline_log = f'controlled-{number}-offline.log'
        receipt = f'compatibility/controlled_{number}-primary.json'
        analysis_log = f'compatibility/controlled_{number}-analysis.log'
        negative_log = f'compatibility/controlled_{number}-negative.log'
        positive_audit = f'delivery-proof/controlled_{number}-positive.log'
        negative_audit = f'delivery-proof/controlled_{number}-negative.log'
        audit_script = 'native/delivery_audit.py'
        entry = dict(source)
        fallback = dict(source['candidates'][0])
        fallback_log = f'compatibility/controlled_{number}-fallback1-offline.log'
        fallback_receipt = f'compatibility/controlled_{number}-fallback1.json'
        fallback_analysis = f'compatibility/controlled_{number}-fallback1-analysis.log'
        fallback_negative = f'compatibility/controlled_{number}-fallback1-negative.log'
        fallback['offline'] = {
            'command': '.venv-cpu/bin/python -B runtime.py offline --manifest work/' + AID +
                       '/draft-mounted-sidewalk-manifest.json --case ' + case +
                       ' --candidate fallback1 --output .runtime-work/c230207a-output/controlled-' +
                       str(number) + '-fallback1-offline-v5',
            'construction_sha256': fallback['construction_sha256'],
            'exit_code': 0, 'log': fallback_log, 'log_sha256': sha(HERE / fallback_log)}
        fallback['compatibility'] = {'receipt': fallback_receipt,
                                     'sha256': sha(HERE / fallback_receipt),
                                     'log': fallback_analysis,
                                     'negative_log': fallback_negative}
        entry['candidates'] = [fallback]
        entry.update(
            measurement_procedure={'entrypoint': 'finalize.py',
                                   'output_schema': 'c230207-sidewalk-source-analysis-v1'},
            native_handoff={'python_env_var': 'CARLA_PYTHON', 'host_env_var': 'CARLA_HOST',
                            'port_env_var': 'CARLA_PORT'},
            offline={'command': '.venv-cpu/bin/python -B runtime.py offline --manifest work/' + AID +
                     '/draft-mounted-sidewalk-manifest.json --case ' + case +
                     ' --output .runtime-work/c230207a-output/controlled-' + str(number) + '-primary-offline-v5',
                     'construction_sha256': source['construction_sha256'],
                     'exit_code': 0, 'log': offline_log, 'log_sha256': sha(HERE / offline_log)},
            compatibility={'receipt': receipt, 'sha256': sha(HERE / receipt),
                           'log': analysis_log, 'negative_log': negative_log},
            negative={'log': negative_log},
            acquisition={name: {'entrypoint': 'finalize.py',
                                'method': 'joined original Native bicycle/operator, sign and sidewalk sources',
                                'evidence': 'bicycle-poses.jsonl,restriction-context.json,video_frames.jsonl'}
                         for name in ('cycle_pose', 'restriction_context')},
            delivery_acceptance={'case_id': case, 'sets': ['full-train'],
                                 'checks': ['native_source', 'all_participants', 'time_join',
                                            'full_video_decode', 'actual_pixels', 'physical_completion'],
                                 'script': audit_script, 'script_sha256': sha(HERE / audit_script),
                                 'command': '.venv-cpu/bin/python -B work/' + AID + '/' + audit_script +
                                            ' --case ' + case + ' --selftest',
                                 'test_exit_code': 0, 'test_log': positive_audit,
                                 'test_log_sha256': sha(HERE / positive_audit),
                                 'negative_command': '.venv-cpu/bin/python -B work/' + AID + '/' + audit_script +
                                                     ' --case ' + case + ' --negative-selftest',
                                 'negative_exit_code': 1,
                                 'negative_expected_error': 'Missing delivery source: restriction-context.json',
                                 'negative_log': negative_audit,
                                 'negative_log_sha256': sha(HERE / negative_audit)},
            post_capture={'recorded_only': True,
                          'command': '.venv-cpu/bin/python -B runtime.py process-saved --manifest work/' + AID +
                                     '/draft-selected-execution-manifest.json --case ' + case +
                                     ' --attempt "$ATTEMPT" --output "$SAVED_OUTPUT" --library runtime/library'
                                     ' --validator "$ADAPTER_CHECK" --owner-release-receipt "$OWNER_RELEASE_RECEIPT"',
                          'feedback_command': 'cat "$SAVED_OUTPUT/feedback.json"'})
        entries.append(entry)
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': AID,
                'runtime_manifest_sha256': draft['runtime_manifest_sha256'],
                'status': 'partial_cpu_draft', 'delivery_ready': False,
                'cases': entries}
    path = HERE / 'draft-selected-execution-manifest.json'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    return {'manifest_sha256': sha(path), 'case_ids': [e['case_id'] for e in entries],
            'delivery_ready': False}


if __name__ == '__main__':
    print(json.dumps(bind(), sort_keys=True))
