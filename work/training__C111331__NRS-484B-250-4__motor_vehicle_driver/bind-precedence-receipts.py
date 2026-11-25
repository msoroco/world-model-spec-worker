"""Bind exact precedence CPU proofs after the saved-only runs have completed."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BASE = ROOT.name
MANIFEST = ROOT / 'precedence-construction-manifest.json'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest = json.loads(MANIFEST.read_text())
for entry in manifest['cases']:
    suffix = entry['case_id'].removeprefix(BASE + '__')
    if suffix not in {'prior_stop_yield', 'prior_stop_no_yield', 'inside_vehicle_no_yield'}:
        continue
    for candidate, target in (('primary', entry), ('fallback1', entry['candidates'][0])):
        local = ROOT / 'precedence' / suffix / candidate
        rel = local.relative_to(ROOT).as_posix()
        files = {name: local / name for name in (
            'offline.log', 'compatibility.json', 'analysis.log',
            'negative-analysis.log', 'processing.json')}
        if not all(path.is_file() for path in files.values()):
            raise ValueError('Missing exact CPU proof: ' + rel)
        compatibility = json.loads(files['compatibility.json'].read_text())
        processing = json.loads(files['processing.json'].read_text())
        if (compatibility.get('passed') is not True or
                compatibility.get('case_id') != entry['case_id'] or
                compatibility.get('candidate_id') != candidate or
                compatibility.get('construction_sha256') != target['construction_sha256']):
            raise ValueError('Stale public receipt: ' + rel)
        if (processing.get('passed') is not True or
                processing.get('recorded_only') is not True or
                processing.get('missing_evidence') is not False or
                processing.get('candidate_id') != candidate):
            raise ValueError('Stale saved receipt: ' + rel)
        target['offline'] = {
            'command': f'.venv-cpu/bin/python runtime.py offline --manifest work/{BASE}/precedence-construction-manifest.json --case {entry["case_id"]} --candidate {candidate} --output .runtime-work/c111331-2504-prec-offline-{suffix}-{candidate} --python "$PWD/.venv-cpu/bin/python"',
            'construction_sha256': target['construction_sha256'],
            'exit_code': 0, 'log': rel + '/offline.log',
            'log_sha256': sha(files['offline.log'])}
        target['compatibility'] = {
            'receipt': rel + '/compatibility.json',
            'sha256': sha(files['compatibility.json']),
            'log': rel + '/analysis.log', 'log_sha256': sha(files['analysis.log']),
            'negative_log': rel + '/negative-analysis.log',
            'negative_log_sha256': sha(files['negative-analysis.log'])}
        if candidate == 'primary':
            entry['negative'] = {'log': rel + '/negative-analysis.log'}
        command = (f'.venv-cpu/bin/python runtime.py process-saved --manifest '
                   f'work/{BASE}/precedence-construction-manifest.json --case '
                   f'{entry["case_id"]} --attempt $ATTEMPT --output $OUTPUT '
                   f'--library runtime/library --validator $DECODER')
        target['saved_processing'] = {
            'receipt': rel + '/processing.json', 'sha256': sha(files['processing.json']),
            'command': command, 'test_exit_code': 0,
            'recorded_only': True, 'missing_evidence': False}
        if candidate == 'primary':
            entry['post_capture'] = {
                'command': command, 'feedback_command': 'cat $OUTPUT/versions/*/feedback.json',
                'recorded_only': True, 'test_exit_code': 0,
                'test_log': rel + '/processing.json',
                'test_log_sha256': sha(files['processing.json'])}
manifest['status'] = 'selected_cpu_precedence_processing_passed_delivery_partial'
MANIFEST.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
