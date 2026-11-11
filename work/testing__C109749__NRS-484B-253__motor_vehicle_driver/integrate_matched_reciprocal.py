"""Promote the matched reciprocal CPU drafts into the canonical partial package."""
import copy
import hashlib
import json
from pathlib import Path

folder = Path(__file__).resolve().parent
aid = folder.name
suffixes = ('reciprocal_yield_matched', 'reciprocal_no_yield')


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


paths = {name: folder / name for name in (
    'case-plan.json', 'proposals/cases.json', 'execution-manifest.json',
    'proposals/semantic-index.json')}
plan, proposals, manifest, index = (read(paths[name]) for name in paths)
assert not any(row['case_id'].endswith(tuple('__' + x for x in suffixes))
               for row in manifest['cases'])

for suffix in suffixes:
    case = aid + '__' + suffix
    rel = Path('cases') / suffix
    draft = folder / rel
    construction = read(draft / 'construction.json')
    draft_manifest = read(draft / 'draft-manifest.json')['cases'][0]
    assert construction['case_id'] == draft_manifest['case_id'] == case
    plan['cases'].append({
        'case_id': case, 'target_law_id': 'NRS-484B-253',
        'gap_ids': ['gap-conditional-branch'],
        'status': 'tentative_new_capture_pending_accepted_source_review',
        'objective': ('Matched later opposing actor stops outside while the subject turns'
                      if suffix == 'reciprocal_yield_matched' else
                      'Matched later opposing actor enters the junction while the subject turns')
        + '; original Native motion, visibility, and legal meaning remain unverified.'})
    for disposition in plan['requirement_dispositions']:
        if disposition['status'] == 'selected_required':
            disposition['case_ids'].append(case)

    source = next(row for row in proposals['cases'] if row['case_id'].endswith(
        '__reciprocal_yield_after_turn' if suffix == 'reciprocal_yield_matched'
        else '__reciprocal_continues_after_turn'))
    proposal = copy.deepcopy(source)
    proposal['case_id'] = case
    proposal['recording_description'] = construction['recording_description']
    proposal['paired_probe_id'] = 'c109749-controlled-reciprocal-matched'
    proposal['deliberate_differences'] = ['later_opposing_braking_policy']
    proposal['variable_assignments']['later_opposing_braking_policy']['value'] = (
        suffix == 'reciprocal_yield_matched')
    proposal['rationale'] = plan['cases'][-1]['objective']
    proposal['probe']['target_value_or_branch'] = plan['cases'][-1]['objective']
    proposals['cases'].append(proposal)

    def proof(label, digest):
        prefix = rel / 'proofs' / label
        offline_log = rel / (label + '-offline.log')
        compat_log = rel / (label + '-compatibility.log')
        saved_log = rel / (label + '-saved.log')
        offline = {'command': 'pending canonical rebind', 'exit_code': 0,
                   'log': str(offline_log), 'log_sha256': sha(folder / offline_log),
                   'construction_sha256': digest}
        compatible = {'receipt': str(prefix / 'compatibility.json'),
                      'sha256': sha(folder / prefix / 'compatibility.json'),
                      'log': str(prefix / 'analysis.log'),
                      'negative_log': str(prefix / 'negative-analysis.log'),
                      'replay_command': 'pending canonical rebind',
                      'replay_log': str(compat_log)}
        saved = {'recorded_only': True, 'command': 'pending canonical rebind',
                 'feedback_command': 'pending canonical rebind',
                 'test_log': str(saved_log), 'test_log_sha256': sha(folder / saved_log),
                 'test_exit_code': 0}
        return offline, compatible, saved

    acquisition = {}
    config = read(draft / 'config.json')
    for atom in config['required_atoms']:
        acquisition[atom] = {
            'entrypoint': 'capture_sources.py' if atom in ('sig.turn_indicator', 'rel.oncoming') else 'runner.py',
            'method': 'original actor readback' if atom in ('sig.turn_indicator', 'rel.oncoming') else 'original Native frame',
            'evidence': 'interaction_history.jsonl and Native frame join' if atom in ('sig.turn_indicator', 'rel.oncoming') else 'trace.jsonl and capture/evidence.jsonl'}
    for channel in construction['recording_description']['channels']:
        acquisition[channel['name']] = {'entrypoint': 'finalizer.py',
            'method': 'rebuild from original interaction history and geometry',
            'evidence': 'interaction_history.jsonl and intersection_geometry.json'}

    entry = {'case_id': case, 'kind': 'delivery',
             'construction': str(rel / 'construction.json'),
             'construction_sha256': sha(draft / 'construction.json'),
             'measurement_procedure': {'entrypoint': 'finalizer.py'},
             'candidate_risk': draft_manifest['candidate_risk'],
             'measurement_contract': str(rel / 'measurement-contract.json'),
             'fixture_recipe': f'work/{aid}/{rel}/diagnostic-recipe.json',
             'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
             'acquisition': acquisition, 'candidates': []}
    entry['offline'], entry['compatibility'], entry['post_capture'] = proof('primary', entry['construction_sha256'])
    entry['negative'] = {'log': entry['compatibility']['negative_log']}
    for candidate in draft_manifest['candidates']:
        row = {key: candidate[key] for key in ('id', 'construction_sha256', 'trigger', 'changed_knobs')}
        row['construction'] = str(rel / candidate['construction'])
        row['offline'], row['compatibility'], row['post_capture'] = proof(row['id'], row['construction_sha256'])
        entry['candidates'].append(row)
    physical = rel / 'physical-proofs/receipt.json'
    entry['physical_preparation'] = {'receipt': str(physical), 'sha256': sha(folder / physical)}
    script = rel / 'delivery_audit.py'
    positive = rel / 'delivery-positive.log'
    negative = rel / 'delivery-negative.log'
    stem = suffix.replace('_', '-')
    pos_root = ('.runtime-work/c109749-reciprocal-yield-matched-delivery-v2'
                if suffix == 'reciprocal_yield_matched' else
                '.runtime-work/c109749-reciprocal-no-yield-delivery-v1')
    neg_root = f'.runtime-work/c109749-{stem}-delivery-negative-v1'
    # Draft receipts already bind the fixture attempts. The canonical proof will
    # recheck the same source-bound audit commands and hashes below.
    entry['delivery_acceptance'] = {
        'case_id': case, 'sets': ['demo-test', 'full-test'],
        'checks': ['native_source', 'all_participants', 'time_join',
                   'full_video_decode', 'actual_pixels', 'physical_completion'],
        'script': str(script), 'script_sha256': sha(folder / script),
        'command': f'PYTHONPATH=work/{aid} .venv-cpu/bin/python work/{aid}/{rel}/delivery_fixture_proof.py --case {case} --output-root {pos_root}',
        'test_exit_code': 0, 'test_log': str(positive),
        'test_log_sha256': sha(folder / positive),
        'negative_command': f'PYTHONPATH=work/{aid} .venv-cpu/bin/python work/{aid}/{rel}/delivery_fixture_proof.py --case {case} --output-root {neg_root} --negative-source-root {pos_root}',
        'negative_exit_code': 1,
        'negative_expected_error': 'Sealed original source',
        'negative_log': str(negative), 'negative_log_sha256': sha(folder / negative)}
    manifest['cases'].append(entry)

plan['comparisons'].append({
    'comparison_id': 'reciprocal_matched_response',
    'case_ids': [aid + '__' + x for x in suffixes],
    'fixed_conditions': ['same selected junction, subject and initial opposing motion',
                         'same later opposing trajectory before subject turn onset',
                         'same 20 Hz, 45-second capture and four source cameras'],
    'deliberate_differences': ['later_opposing_braking_policy: stop outside versus continue into junction'],
    'source_review_status': 'tentative; synthetic diagnostic comparison only; original Native motion unverified'})
write(paths['case-plan.json'], plan)
write(paths['proposals/cases.json'], proposals)
index['stages']['cases']['sha256'] = sha(paths['proposals/cases.json'])
write(paths['proposals/semantic-index.json'], index)
write(paths['execution-manifest.json'], manifest)
print(json.dumps({'canonical_cases': len(manifest['cases']), 'status': 'partial; proofs need canonical rebind'}))
