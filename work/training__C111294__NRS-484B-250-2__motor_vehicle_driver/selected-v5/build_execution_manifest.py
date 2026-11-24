"""Bind selected V5 CPU diagnostics to the exact two-case delivery handoff."""
import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
REPO = BASE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def proof_ref(path):
    if not path.is_file():
        raise ValueError('missing CPU proof: ' + str(path))
    return path.relative_to(BASE).as_posix()


def build():
    manifest = json.loads((BASE / 'selected-v5-manifest.json').read_text())
    script = BASE / 'selected-v5/audit_delivery.py'
    comparison = BASE / 'selected-v3/audit_comparison.py'
    comparison_positive = BASE / 'selected-v3/comparison-positive.log'
    comparison_negative = BASE / 'selected-v3/comparison-negative.log'
    for entry in manifest['cases']:
        case_id = entry['case_id']
        suffix = case_id.rsplit('__', 1)[1]
        construction = BASE / entry['construction']
        if sha(construction) != entry['construction_sha256']:
            raise ValueError('selected construction changed')
        chosen = json.loads(construction.read_text())
        channels = [x['name'] for x in chosen['recording_description']['channels']]
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
        entry['acquisition'] = {
            term: {'entrypoint': 'finalize.py',
                   'method': '20 Hz source-joined actor body, frame map and four-view capture evidence',
                   'evidence': 'actor-history.json; video_frames.jsonl; capture/evidence.jsonl; four named source views'}
            for term in channels}
        for candidate, choice in [('primary', entry), *[(x['id'], x) for x in entry['candidates']]]:
            selected = BASE / 'selected-v5' / suffix / candidate
            log = selected / 'proofs/offline.log'
            choice['offline'] = {
                'exit_code': 0, 'construction_sha256': choice['construction_sha256'],
                'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{BASE.name}/execution-manifest.json --case {case_id} --candidate {candidate} --output "$OUTPUT" --python "$CARLA_PYTHON"',
                'log': proof_ref(log), 'log_sha256': sha(log)}
            public = selected / 'proofs/compatibility.json'
            analysis = selected / 'proofs/public-analysis.log'
            negative = selected / 'proofs/negative-analysis.log'
            choice['compatibility'] = {'receipt': proof_ref(public), 'sha256': sha(public),
                                       'log': proof_ref(analysis), 'negative_log': proof_ref(negative)}
            if candidate == 'primary':
                entry['negative'] = {'log': proof_ref(negative)}
                saved = selected / 'proofs/saved-processing.json'
                entry['post_capture'] = {
                    'recorded_only': True,
                    'command': f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{BASE.name}/execution-manifest.json --case {case_id} --attempt "$ATTEMPT" --output "$OUTPUT" --library runtime/library --validator "$DECODER"',
                    'feedback_command': 'inspect "$OUTPUT/feedback.json" on failure',
                    'test_log': proof_ref(saved), 'test_log_sha256': sha(saved),
                    'test_exit_code': 0}
        physical = BASE / 'selected-v5/physical-proofs' / suffix / 'proof.json'
        entry['physical_preparation'] = {'receipt': proof_ref(physical), 'sha256': sha(physical)}
        positive = BASE / 'selected-v5/delivery-proofs' / suffix / 'positive.log'
        rejected = BASE / 'selected-v5/delivery-proofs' / suffix / 'negative.log'
        entry['delivery_acceptance'] = {
            'case_id': case_id, 'sets': ['demo-train', 'full-train'],
            'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode',
                       'actual_pixels', 'physical_completion'],
            'script': proof_ref(script), 'script_sha256': sha(script),
            'command': f'.venv-cpu/bin/python work/{BASE.name}/selected-v5/audit_delivery.py {case_id}',
            'test_exit_code': 0, 'test_log': proof_ref(positive), 'test_log_sha256': sha(positive),
            'negative_command': f'.venv-cpu/bin/python work/{BASE.name}/selected-v5/audit_delivery.py {case_id} --negative',
            'negative_exit_code': 1, 'negative_expected_error': 'missing actor-history source',
            'negative_log': proof_ref(rejected), 'negative_log_sha256': sha(rejected),
            'cpu_scope': 'synthetic diagnostic; original Native capture and legal applicability pending'}
        entry['comparison_audit'] = {
            'script': proof_ref(comparison), 'script_sha256': sha(comparison),
            'command': f'.venv-cpu/bin/python work/{BASE.name}/selected-v3/audit_comparison.py',
            'test_log': proof_ref(comparison_positive), 'test_log_sha256': sha(comparison_positive),
            'test_exit_code': 0,
            'negative_command': f'.venv-cpu/bin/python work/{BASE.name}/selected-v3/audit_comparison.py --probe-other-history changed',
            'negative_log': proof_ref(comparison_negative), 'negative_log_sha256': sha(comparison_negative),
            'negative_exit_code': 1, 'negative_expected_error': 'Other participant changed'}
    manifest['status'] = 'selected_cpu_proven_original_pending'
    path = BASE / 'execution-manifest.json'
    path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'execution_manifest_sha256': sha(path), 'cases': len(manifest['cases'])}))


if __name__ == '__main__':
    build()
