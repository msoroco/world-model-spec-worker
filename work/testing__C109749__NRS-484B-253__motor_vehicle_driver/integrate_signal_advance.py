"""Integrate the matched 30.48 m signal cases into the canonical partial package."""
import copy
import hashlib
import json
import shutil
from pathlib import Path

folder = Path(__file__).resolve().parent
repo = folder.parent.parent
aid = folder.name
suffixes = ('signal_advance_100_at', 'signal_advance_100_omitted')
paths = {name: folder / name for name in (
    'case-plan.json', 'proposals/cases.json', 'execution-manifest.json',
    'proposals/semantic-index.json', 'config.json')}


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + '\n')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


plan, proposals, manifest, index = (read(paths[name]) for name in
                                     ('case-plan.json', 'proposals/cases.json',
                                      'execution-manifest.json', 'proposals/semantic-index.json'))
if any(row['case_id'].endswith(tuple('__' + suffix for suffix in suffixes))
       for row in manifest['cases']):
    raise ValueError('Signal-advance cases already integrated')
backup = repo / '.runtime-work/c109749-pre-signal-advance-integration-v1'
if backup.exists():
    raise ValueError('Use a fresh integration backup root')
backup.mkdir(parents=True)
for name, path in paths.items():
    target = backup / name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(path, target)

for suffix in suffixes:
    case = aid + '__' + suffix
    rel = Path('cases') / suffix
    draft = folder / rel
    construction = read(draft / 'construction.json')
    selected = read(draft / 'draft-manifest.json')['cases'][0]
    exact = read(draft / 'exact-proof-receipt.json')
    delivery = read(draft / 'delivery-proof-receipt.json')
    if (not construction['case_id'] == selected['case_id'] == case or
            exact['case_id'] != case or delivery['case_id'] != case):
        raise ValueError('Signal draft identity differs: ' + suffix)
    objective = ('Observed continuous 30.48 m left indication before the occupied-junction yield turn'
                 if suffix == 'signal_advance_100_at' else
                 'Matched occupied-junction yield turn with the extended approach and left indication omitted')
    plan['cases'].append({'case_id': case, 'target_law_id': 'NRS-484B-253',
                          'gap_ids': ['gap-conditional-branch'],
                          'status': 'tentative_new_capture_pending_accepted_source_review',
                          'objective': objective + '; Native motion, district classification, visibility and legal meaning remain unverified.'})
    for disposition in plan['requirement_dispositions']:
        if disposition['status'] == 'selected_required':
            disposition['case_ids'].append(case)
    source_suffix = 'inside_yield' if suffix == 'signal_advance_100_at' else 'signal_omitted'
    source = next(row for row in proposals['cases']
                  if row['case_id'].endswith('__' + source_suffix))
    proposal = copy.deepcopy(source)
    proposal['case_id'] = case
    proposal['recording_description'] = construction['recording_description']
    proposal['paired_probe_id'] = 'c109749-controlled-signal-advance-100ft'
    proposal['deliberate_differences'] = ['left_signal_enabled']
    proposal['variable_assignments']['left_signal_enabled']['value'] = suffix == 'signal_advance_100_at'
    proposal['rationale'] = objective + '; no legal sufficiency claim.'
    proposal['probe']['target_value_or_branch'] = objective
    proposals['cases'].append(proposal)

    config = read(draft / 'config.json')
    acquisition = {}
    for atom in config['required_atoms']:
        acquisition[atom] = {
            'entrypoint': 'capture_sources.py' if atom in ('sig.turn_indicator', 'rel.oncoming') else 'runner.py',
            'method': 'original actor readback' if atom in ('sig.turn_indicator', 'rel.oncoming') else 'original Native frame',
            'evidence': 'interaction_history.jsonl and Native frame join' if atom in ('sig.turn_indicator', 'rel.oncoming')
                        else 'trace.jsonl and capture/evidence.jsonl'}
    for channel in construction['recording_description']['channels']:
        acquisition[channel['name']] = {'entrypoint': 'finalizer.py',
                                        'method': 'rebuild from original interaction history and geometry',
                                        'evidence': 'interaction_history.jsonl and intersection_geometry.json'}

    def proof(label, item):
        prefix = rel / 'proofs' / label
        offline_log = rel / (label + '-offline.log')
        compat_log = prefix / 'exact-compatibility-command.log'
        saved_log = prefix / 'saved-command.log'
        offline = {'command': 'pending canonical replay', 'exit_code': 0,
                   'log': str(offline_log), 'log_sha256': sha(folder / offline_log),
                   'construction_sha256': item['construction_sha256']}
        compatible = {'receipt': str(prefix / 'compatibility.json'),
                      'sha256': sha(folder / prefix / 'compatibility.json'),
                      'log': str(prefix / 'exact-compatibility-analysis.log'),
                      'negative_log': str(prefix / 'negative-analysis.log'),
                      'replay_command': 'pending canonical replay',
                      'replay_log': str(compat_log)}
        saved = {'recorded_only': True, 'command': 'pending canonical replay',
                 'feedback_command': 'pending canonical replay',
                 'test_log': str(saved_log),
                 'test_log_sha256': sha(folder / saved_log), 'test_exit_code': 0}
        return offline, compatible, saved

    entry = {'case_id': case, 'kind': 'delivery',
             'construction': str(rel / 'construction.json'),
             'construction_sha256': sha(draft / 'construction.json'),
             'measurement_procedure': {'entrypoint': 'finalizer.py'},
             'candidate_risk': selected['candidate_risk'],
             'measurement_contract': str(rel / 'measurement-contract.json'),
             'fixture_recipe': f'work/{aid}/{rel}/diagnostic-recipe.json',
             'native_handoff': {'python_env_var': 'CARLA_PYTHON',
                                'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'},
             'acquisition': acquisition, 'candidates': []}
    entry['offline'], entry['compatibility'], entry['post_capture'] = proof('primary', entry)
    entry['negative'] = {'log': entry['compatibility']['negative_log']}
    for candidate in selected['candidates']:
        row = {key: candidate[key] for key in ('id', 'construction_sha256', 'trigger', 'changed_knobs')}
        row['construction'] = str(rel / candidate['construction'])
        row['offline'], row['compatibility'], row['post_capture'] = proof(row['id'], row)
        entry['candidates'].append(row)
    physical = rel / 'physical-proofs/receipt.json'
    entry['physical_preparation'] = {'receipt': str(physical), 'sha256': sha(folder / physical)}
    positive = rel / 'delivery-positive.log'
    negative = rel / 'delivery-negative.log'
    if suffix == 'signal_advance_100_at':
        script = Path('signal_advance_delivery_audit.py')
        fixture_script = Path('signal_advance_delivery_fixture_proof.py')
        root = '.runtime-work/c109749-signal-advance-delivery-v1'
        negative_root = '.runtime-work/c109749-signal-advance-delivery-negative-v1'
        checks = ['native_source', 'all_participants', 'time_join', 'full_video_decode',
                  'actual_pixels', 'physical_completion', 'signal_advance']
    else:
        script = Path('signal_advance_omitted_delivery_audit.py')
        fixture_script = Path('signal_advance_omitted_delivery_fixture_proof.py')
        root = '.runtime-work/c109749-signal-advance-omitted-delivery-v1'
        negative_root = '.runtime-work/c109749-signal-advance-omitted-delivery-negative-v1'
        checks = ['native_source', 'all_participants', 'time_join', 'full_video_decode',
                  'actual_pixels', 'physical_completion']
    entry['delivery_acceptance'] = {
        'case_id': case, 'sets': ['demo-test', 'full-test'], 'checks': checks,
        'script': str(script), 'script_sha256': sha(folder / script),
        'command': f'.venv-cpu/bin/python work/{aid}/{fixture_script} --case {case} --output-root {root}',
        'test_exit_code': 0, 'test_log': str(positive), 'test_log_sha256': sha(folder / positive),
        'negative_command': f'.venv-cpu/bin/python work/{aid}/{fixture_script} --case {case} '
                            f'--output-root {negative_root} --negative-source-root {root}',
        'negative_exit_code': 1,
        'negative_expected_error': 'Sealed original source changed: interaction_history.jsonl',
        'negative_log': str(negative), 'negative_log_sha256': sha(folder / negative)}
    manifest['cases'].append(entry)

plan['comparisons'].append({'comparison_id': 'signal_advance_100ft_matched',
                            'case_ids': [aid + '__' + suffix for suffix in suffixes],
                            'fixed_conditions': ['same selected junction and all three actor trajectories',
                                                 'same upstream route, 20 Hz/45-second camera plan and turn timing'],
                            'deliberate_differences': ['left_signal_enabled: observed 30.48 m continuous indication versus omitted'],
                            'source_review_status': 'tentative; 900-frame synthetic comparison only; Native motion unverified'})
write(paths['case-plan.json'], plan)
write(paths['proposals/cases.json'], proposals)
index['stages']['cases']['sha256'] = sha(paths['proposals/cases.json'])
write(paths['proposals/semantic-index.json'], index)
write(paths['execution-manifest.json'], manifest)

# The root selected construction enumerates all canonical case IDs. Preserve its
# implementation and adjust only that enumerated list before exact replay.
supported = [row['case_id'] for row in manifest['cases']]
root_config = read(paths['config.json'])
root_config['supported_case_ids'] = supported
write(paths['config.json'], root_config)
first = manifest['cases'][0]
for item in [first, *first['candidates']]:
    path = folder / item['construction']
    bundle = read(path)
    for file in bundle['files']:
        if file['path'] == 'config.json':
            config = json.loads(file['content'])
            config['supported_case_ids'] = supported
            file['content'] = json.dumps(config, indent=2) + '\n'
    write(path, bundle)
    item['construction_sha256'] = sha(path)
write(paths['execution-manifest.json'], manifest)
print(json.dumps({'canonical_cases': len(manifest['cases']),
                  'changed_existing_constructions': 4,
                  'new_constructions': 8,
                  'status': 'partial; canonical replay required'}))
