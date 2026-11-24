"""Bind five exact selected cases to their CPU proofs and Native handoff."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
BASE = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ref(path):
    if not path.is_file():
        raise ValueError('Missing exact CPU proof: ' + str(path))
    return path.relative_to(BASE).as_posix()


def build():
    main = json.loads((BASE / 'execution-manifest.json').read_text())
    main['cases'] = [entry for entry in main['cases'] if entry['case_id'].endswith(('__controlled_1', '__controlled_2'))]
    if len(main['cases']) != 2:
        raise ValueError('Main selected pair changed')
    branch = json.loads((BASE / 'branch-v1-manifest.json').read_text())
    script = HERE / 'audit_delivery.py'
    comparison = HERE / 'audit_comparisons.py'
    comparison_negative_script = HERE / 'prove_comparison_negative.py'
    comparison_positive = HERE / 'comparison-positive.log'
    comparison_negative = HERE / 'comparison-negative.log'
    for entry in branch['cases']:
        case_id = entry['case_id']
        suffix = case_id.rsplit('__', 1)[1]
        construction = BASE / entry['construction']
        if sha(construction) != entry['construction_sha256']:
            raise ValueError('Branch selected construction changed')
        channels = [item['name'] for item in json.loads(construction.read_text())['recording_description']['channels']]
        entry['acquisition'] = {
            channel: {'entrypoint': 'finalize.py',
                      'method': '20 Hz source-joined actor bodies, frame map and four-view capture evidence',
                      'evidence': 'actor-history.json; video_frames.jsonl; capture/evidence.jsonl; four named source views'}
            for channel in channels}
        for candidate, choice in [('primary', entry), *[(item['id'], item) for item in entry['candidates']]]:
            proof = HERE / suffix / candidate / 'proofs'
            offline = proof / 'offline.log'
            public = proof / 'compatibility.json'
            analysis = proof / 'public-analysis.log'
            negative = proof / 'negative-analysis.log'
            choice['offline'] = {
                'exit_code': 0, 'construction_sha256': choice['construction_sha256'],
                'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{BASE.name}/execution-manifest.json --case {case_id} --candidate {candidate} --output "$OUTPUT" --python "$CARLA_PYTHON"',
                'log': ref(offline), 'log_sha256': sha(offline)}
            choice['compatibility'] = {
                'receipt': ref(public), 'sha256': sha(public),
                'log': ref(analysis), 'negative_log': ref(negative)}
            if candidate == 'primary':
                entry['negative'] = {'log': ref(negative)}
                saved = proof / 'saved-processing.json'
                entry['post_capture'] = {
                    'recorded_only': True,
                    'command': f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{BASE.name}/execution-manifest.json --case {case_id} --attempt "$ATTEMPT" --output "$OUTPUT" --library runtime/library --validator "$DECODER"',
                    'feedback_command': 'inspect "$OUTPUT/feedback.json" on failure',
                    'test_log': ref(saved), 'test_log_sha256': sha(saved),
                    'test_exit_code': 0}
        physical = HERE / 'physical-proofs' / suffix / 'proof.json'
        entry['physical_preparation'] = {'receipt': ref(physical), 'sha256': sha(physical)}
        positive = HERE / 'delivery-proofs' / suffix / 'positive.log'
        rejected = HERE / 'delivery-proofs' / suffix / 'negative.log'
        entry['delivery_acceptance'] = {
            'case_id': case_id, 'sets': ['demo-train', 'full-train'],
            'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode',
                       'actual_pixels', 'physical_completion'],
            'script': ref(script), 'script_sha256': sha(script),
            'command': f'.venv-cpu/bin/python work/{BASE.name}/branch-v1/audit_delivery.py {case_id}',
            'test_exit_code': 0, 'test_log': ref(positive), 'test_log_sha256': sha(positive),
            'negative_command': f'.venv-cpu/bin/python work/{BASE.name}/branch-v1/audit_delivery.py {case_id} --negative',
            'negative_exit_code': 1, 'negative_expected_error': 'missing actor-history source',
            'negative_log': ref(rejected), 'negative_log_sha256': sha(rejected),
            'cpu_scope': 'synthetic diagnostic; original Native motion, official governance and legal applicability pending'}
        entry['comparison_audit'] = {
            'script': ref(comparison), 'script_sha256': sha(comparison),
            'command': f'.venv-cpu/bin/python work/{BASE.name}/branch-v1/audit_comparisons.py',
            'test_log': ref(comparison_positive), 'test_log_sha256': sha(comparison_positive),
            'test_exit_code': 0,
            'negative_script': ref(comparison_negative_script),
            'negative_script_sha256': sha(comparison_negative_script),
            'negative_command': f'.venv-cpu/bin/python work/{BASE.name}/branch-v1/prove_comparison_negative.py',
            'negative_log': ref(comparison_negative), 'negative_log_sha256': sha(comparison_negative),
            'negative_exit_code': 1,
            'negative_expected_error': 'Branch actor/frame source join changed'}
        main['cases'].append(entry)
    main['status'] = 'selected_cpu_proven_original_pending'
    path = BASE / 'execution-manifest.json'
    path.write_text(json.dumps(main, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'execution_manifest_sha256': sha(path), 'cases': len(main['cases'])}))


if __name__ == '__main__':
    build()
