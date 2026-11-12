"""Independent source/hash audit for C104538's refreshed semantic-bound matrix."""
import copy
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')
SUFFIXES = ('below_500_ft', 'at_500_ft', 'above_500_ft')
CHECKS = {'actual_analysis', 'native_validation', 'mandatory_observations',
          'lean_decoder', 'render', 'final_decode', 'acquisition_unchanged',
          'derived_outputs_rebuilt', 'four_camera_sources', 'selected_measurements',
          'negative_case_source'}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit(summary=None):
    summary = summary or read(HERE/'update023-semantic-bound-matrix.json')
    offline = read(HERE/'update023-semantic-bound-offline.json')
    manifest = read(HERE/'execution-manifest.json')
    proposal = read(HERE/'proposals/cases.json')
    manifest_sha, proposal_sha = sha(HERE/'execution-manifest.json'), sha(HERE/'proposals/cases.json')
    require(summary.get('format') == 'c104538-semantic-bound-matrix-v1' and
            offline.get('format') == 'c104538-semantic-bound-offline-v1' and
            summary.get('manifest_sha256') == offline.get('manifest_sha256') == manifest_sha and
            summary.get('proposal_sha256') == offline.get('proposal_sha256') == proposal_sha ==
                manifest['selection_review']['proposal_sha256'],
            'Current semantic and manifest source binding changed')
    require(summary.get('original_native_proven') is False and
            summary.get('physical_or_legal_acceptance') is False and
            offline.get('simulation_started') is False,
            'Diagnostic proof promoted to physical acceptance')
    selected_cases = {c['case_id']: c for c in proposal['cases'] if c['target_type'] != 'baseline'}
    require(len(selected_cases) == 3 and {e['case_id'] for e in manifest['cases']} == set(selected_cases),
            'Selected semantic cases differ from manifest')
    rows = {(r['case_id'], r['candidate_id']): r for r in summary['results']}
    off_rows = {(r['case_id'], r['candidate_id']): r for r in offline['results']}
    require(len(rows) == len(off_rows) == 12, 'Missing or duplicate exact candidate proof')
    limits, roads, traces, evidence = [], set(), set(), set()
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.rsplit('__', 1)[-1]
        require(suffix in SUFFIXES and entry['kind'] == 'delivery', 'Wrong selected case kind')
        obstruction = read(HERE/'draft-sightline'/suffix/'obstruction.json')
        limits.append(round(1000*math.acos(obstruction['inner_radius_m']/500)/.3048))
        require(selected_cases[case]['variable_assignments']['authored_sightline_limit_ft']['value'] == limits[-1],
                'Canonical case differs from authored obstruction source')
        for candidate in CANDIDATES:
            selected = (entry if candidate == 'primary' else
                        next(item for item in entry['candidates'] if item['id'] == candidate))
            key = (case, candidate)
            require(key in rows and key in off_rows, 'Missing selected candidate')
            row, off = rows[key], off_rows[key]
            require(sha(HERE/selected['construction']) == selected['construction_sha256'] ==
                    row['construction_sha256'] == off['construction_sha256'],
                    'Selected construction changed')
            require(row['manifest_sha256'] == off['manifest_sha256'] == manifest_sha and
                    row['proposal_sha256'] == off['proposal_sha256'] == proposal_sha,
                    'Candidate uses another manifest/proposal')
            require(off['offline_passed'] is True and off['simulation_started'] is False and
                    sha(HERE/off['log']) == off['log_sha256'], 'Exact offline proof changed')
            offline_receipt = read(HERE/off['log'])
            require(offline_receipt['offline_passed'] is True and
                    offline_receipt['case_id'] == case and
                    offline_receipt['candidate_id'] == candidate,
                    'Offline receipt identity changed')
            recipe = HERE/f'update015-{suffix}-{candidate}-recipe.json'
            fixture = read(HERE/f'update015-{suffix}-{candidate}-diagnostic.json')
            require(read(recipe)['generator']['sha256'] == sha(HERE/f'update015-{suffix}-{candidate}-diagnostic.json'),
                    'Candidate diagnostic source changed')
            context = json.loads(fixture['files']['native-construction-context.json'])
            require(context['case_id'] == case and context['candidate_id'] == candidate,
                    'Candidate diagnostic identity changed')
            for target, name in ((roads, 'road.xodr'), (traces, 'trace.jsonl'),
                                 (evidence, 'capture/evidence.jsonl')):
                target.add(hashlib.sha256(fixture['files'][name].encode()).hexdigest())
            folder = HERE/'update023-selected-proofs'/suffix/candidate
            for name, expected in row['proofs'].items():
                require(sha(folder/name) == expected, 'Retained proof changed: '+name)
            selection, compat, saved = (read(folder/name) for name in
                                       ('candidate-selection.json', 'compatibility.json', 'processing.json'))
            require(selection['manifest_sha256'] == manifest_sha and
                    selection['case_id'] == case and
                    selection['candidate_id'] == candidate and
                    selection['construction_sha256'] == selected['construction_sha256'],
                    'Candidate selection changed')
            require(compat['passed'] is True and CHECKS <= set(compat['checks']) and
                    compat['case_id'] == case and compat['candidate_id'] == candidate and
                    compat['construction_sha256'] == selected['construction_sha256'] and
                    compat['fixture_recipe_sha256'] == sha(recipe) and
                    compat['negative_removed'] == 'native_body_history.jsonl' and
                    compat['negative_error_contains'] in (folder/'negative.log').read_text(),
                    'Compatibility proof incomplete')
            require(saved['passed'] is True and saved['originals_preserved'] is True and
                    saved['missing_evidence'] is False and
                    saved['case_id'] == case and saved['candidate_id'] == candidate and
                    saved['native_revision']['construction_sha256'] == selected['construction_sha256'] and
                    saved['physical_acceptance_claimed'] is False and
                    saved['legal_acceptance_claimed'] is False,
                    'Saved processing proof changed')
            for name, keyname in (('analysis.log', 'log_sha256'),
                                  ('negative.log', 'negative_log_sha256')):
                require(sha(folder/name) == compat[keyname], 'Compatibility log changed')
            require(sha(HERE/row['compatibility_log']) == row['compatibility_log_sha256'] and
                    sha(HERE/row['saved_log']) == row['saved_log_sha256'],
                    'Command log changed')
    require(sorted(limits) == [450, 500, 550] and
            len(roads) == len(traces) == len(evidence) == 1,
            'Controlled authored sweep or fixed diagnostic context changed')
    return {'selected_cases': 3, 'candidate_cpu_chains': 12,
            'authored_center_reference_limits_ft': sorted(limits),
            'fixed_road_trace_evidence': True, 'original_native_visibility_proven': False,
            'accepted_comparisons': 0}


if __name__ == '__main__':
    positive = audit()
    source = read(HERE/'update023-semantic-bound-matrix.json')
    negatives = 0
    for name in ('missing_candidate', 'stale_proposal', 'false_acceptance'):
        changed = copy.deepcopy(source)
        if name == 'missing_candidate':
            changed['results'].pop()
        elif name == 'stale_proposal':
            changed['proposal_sha256'] = '0'*64
        else:
            changed['physical_or_legal_acceptance'] = True
        try:
            audit(changed)
        except (ValueError, KeyError):
            negatives += 1
        else:
            raise AssertionError('Accepted '+name)
    positive['negative_rejections'] = negatives
    path = HERE/'update023-semantic-bound-matrix-audit.json'
    path.write_text(json.dumps(positive, indent=2)+'\n')
    print(json.dumps(positive, sort_keys=True))
