"""Bind the unchanged-manifest CPU reproofs and diagnostic readiness proofs."""
import hashlib
import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
BASE = ROOT.name
MANIFEST = ROOT / 'stop-reference-construction-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference(path):
    return path.relative_to(ROOT).as_posix()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


manifest = json.loads(MANIFEST.read_text())
older = json.loads((ROOT / 'precedence-construction-manifest.json').read_text())
older_by_id = {item['id']: item for item in older['cases']}
script_sha = sha(ROOT / 'delivery_audit.py')
for entry in manifest['cases']:
    suffix = entry['id']
    case = entry['case_id']
    if suffix in older_by_id:
        delivery = older_by_id[suffix]['delivery_acceptance'].copy()
        delivery['script_sha256'] = script_sha
    else:
        folder = ROOT / 'precedence' / suffix
        delivery = {
            'case_id': case,
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'command': f'.venv-cpu/bin/python work/{BASE}/delivery_audit.py --case {case} --self-test',
            'negative_command': f'.venv-cpu/bin/python work/{BASE}/delivery_audit.py --case {case} --self-test --negative',
            'negative_exit_code': 1,
            'negative_expected_error': 'Missing original source: exact original Native result',
            'negative_log': reference(folder / 'delivery-negative.log'),
            'negative_log_sha256': sha(folder / 'delivery-negative.log'),
            'script': 'delivery_audit.py', 'script_sha256': script_sha,
            'sets': ['demo-train', 'full-train'], 'test_exit_code': 0,
            'test_log': reference(folder / 'delivery-positive.log'),
            'test_log_sha256': sha(folder / 'delivery-positive.log'),
        }
    entry['delivery_acceptance'] = delivery
    entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                               'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
    physical = ROOT / 'physical-preparation' / suffix
    fixture_receipts = []
    for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        result = physical / (kind + '-result.json')
        log = physical / (kind + '.log')
        if not result.is_file() or not log.is_file():
            raise ValueError('Missing physical outcome proof: ' + suffix + ' ' + kind)
        fixture_receipts.append({
            'kind': kind,
            'command': f'.venv-cpu/bin/python work/{BASE}/prove-physical-outcomes.py --case {case} --kind {kind}',
            'exit_code': 0, 'result': reference(result), 'result_sha256': sha(result),
            'log': reference(log), 'log_sha256': sha(log),
        })
    lifecycle = json.loads((REPO / '.runtime-work' / f'c111331-2504-lifecycle-{suffix}.json').read_text())
    proof = {'format': 'worker-physical-preparation',
             'case_id': case, 'construction_sha256': entry['construction_sha256'],
             'fixtures': fixture_receipts, 'lifecycle': lifecycle,
             'scope': 'synthetic CPU diagnostic; original Native physical acceptance pending'}
    proof_path = physical / 'receipt.json'
    write(proof_path, proof)
    entry['physical_preparation'] = {'receipt': reference(proof_path), 'sha256': sha(proof_path)}
    for candidate, target in [('primary', entry), ('fallback1', entry['candidates'][0])]:
        local = ROOT / ('selected-candidates' if suffix.startswith('controlled_') else 'precedence') / suffix / candidate
        compat = REPO / '.runtime-work' / f'c111331-2504-unified-v1-compat-{suffix}-{candidate}'
        if not (compat / 'compatibility.json').is_file():
            compat = REPO / '.runtime-work' / f'c111331-2504-unified-v2-compat-{suffix}-{candidate}'
        saved_root = REPO / '.runtime-work' / f'c111331-2504-unified-v1-saved-{suffix}-{candidate}'
        saved_versions = sorted(saved_root.glob('v*/processing.json'))
        if not saved_versions:
            raise ValueError('Missing saved processing: ' + suffix + ' ' + candidate)
        saved = saved_versions[-1]
        files = {'offline.log': local / 'offline.log',
                 'compatibility.json': compat / 'compatibility.json',
                 'analysis.log': compat / 'compatibility-analysis.log',
                 'negative-analysis.log': compat / 'negative-analysis.log',
                 'processing.json': saved}
        if not all(path.is_file() for path in files.values()):
            raise ValueError('Missing CPU proof: ' + suffix + ' ' + candidate)
        public = json.loads(files['compatibility.json'].read_text())
        processing = json.loads(saved.read_text())
        if not (public.get('passed') is True and public.get('case_id') == case
                and public.get('candidate_id') == candidate
                and public.get('construction_sha256') == target['construction_sha256']
                and processing.get('passed') is True
                and processing.get('candidate_id') == candidate
                and processing.get('recorded_only') is True
                and processing.get('missing_evidence') is False):
            raise ValueError('Stale CPU proof: ' + suffix + ' ' + candidate)
        for name in ('compatibility.json', 'analysis.log', 'negative-analysis.log', 'processing.json'):
            shutil.copyfile(files[name], local / name)
        rel = reference(local)
        target['offline'] = {
            'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{BASE}/stop-reference-construction-manifest.json --case {case} --candidate {candidate} --output .runtime-work/c111331-2504-unified-v1-offline-{suffix}-{candidate} --python "$PWD/.venv-cpu/bin/python"',
            'construction_sha256': target['construction_sha256'], 'exit_code': 0,
            'log': rel + '/offline.log', 'log_sha256': sha(local / 'offline.log')}
        target['compatibility'] = {
            'receipt': rel + '/compatibility.json', 'sha256': sha(local / 'compatibility.json'),
            'log': rel + '/analysis.log', 'log_sha256': sha(local / 'analysis.log'),
            'negative_log': rel + '/negative-analysis.log',
            'negative_log_sha256': sha(local / 'negative-analysis.log')}
        command = (f'.venv-cpu/bin/python runtime.py process-saved --manifest '
                   f'work/{BASE}/stop-reference-construction-manifest.json --case {case} '
                   '--attempt $ATTEMPT --output $OUTPUT --library runtime/library --validator $DECODER')
        target['saved_processing'] = {
            'receipt': rel + '/processing.json', 'sha256': sha(local / 'processing.json'),
            'command': command, 'test_exit_code': 0,
            'recorded_only': True, 'missing_evidence': False}
        if candidate == 'primary':
            entry['negative'] = {'log': rel + '/negative-analysis.log'}
            entry['post_capture'] = {
                'command': command, 'feedback_command': 'cat $OUTPUT/versions/*/feedback.json',
                'recorded_only': True, 'test_exit_code': 0,
                'test_log': rel + '/processing.json',
                'test_log_sha256': sha(local / 'processing.json')}
    entry['kind'] = 'delivery'
manifest['status'] = 'selected_cpu_reproof_passed_original_native_pending'
write(MANIFEST, manifest)
print(sha(MANIFEST))
