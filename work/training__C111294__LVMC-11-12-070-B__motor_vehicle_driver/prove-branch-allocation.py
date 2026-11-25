"""Check selected source coverage of the conditional and crossing phases.

The antecedent's legal satisfaction is reserved for original source review.
"""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
QUOTE = ('Said driver having so yielded may proceed and the drivers of all other '
         'vehicles approaching the intersection on the through highway shall yield '
         'right-of-way to the vehicle about to enter or cross the through highway.')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def phases(rows):
    stopped = [i for i, row in enumerate(rows)
               if row['entrant']['x_m'] < -7 and row['entrant']['speed_mps'] <= .2]
    about = [i for i, row in enumerate(rows)
             if -12 <= row['entrant']['x_m'] <= -7 and row['entrant']['speed_mps'] >= .5]
    crossing = [i for i, row in enumerate(rows)
                if -7 <= row['entrant']['x_m'] <= 7]
    if len(rows) != 600 or len(stopped) < 40 or not about or not crossing:
        raise ValueError('Stopped, about-to-enter and crossing phases required')
    if max(stopped) >= min(about) or min(about) >= min(crossing):
        raise ValueError('Source phase ordering differs')
    if crossing != list(range(min(crossing), max(crossing) + 1)):
        raise ValueError('Continuous entrant crossing required')
    return {'stopped_frames': len(stopped), 'about_first_frame': min(about),
            'cross_first_frame': min(crossing), 'cross_last_frame': max(crossing)}


def reject(rows, index, change):
    mutated = [dict(row) for row in rows]
    mutated[index] = dict(mutated[index])
    mutated[index]['entrant'] = {**mutated[index]['entrant'], **change}
    try:
        phases(mutated)
    except ValueError:
        return True
    raise AssertionError('Missing phase accepted')


def main():
    assignment = json.loads((Path('inputs') / ASSIGNMENT / 'assignment.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    if assignment['law']['text'] != QUOTE or plan['source_law']['text'] != QUOTE:
        raise ValueError('Exact statutory source changed')
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    antecedent_path = HERE / 'selected-antecedent-audit.json'
    antecedent = json.loads(antecedent_path.read_text())
    if sha(manifest_path) != antecedent['manifest_sha256'] or antecedent['lawful_prior_yield_verified']:
        raise ValueError('Selected antecedent audit changed or overclaims legal review')
    selected = {entry['case_id'] for entry in manifest['cases']}
    if len(selected) != 2 or selected != {case['case_id'] for case in plan['cases']}:
        raise ValueError('Exact selected pair differs')
    if any(item['status'] != 'selected_required' or set(item['case_ids']) != selected
           for item in plan['requirement_dispositions']):
        raise ValueError('Requirement allocation differs')
    cases = []
    for case_id in sorted(selected):
        number = case_id.rsplit('_', 1)[-1]
        source = HERE / f'current-v2-probe-{number}-fixture/native_samples.jsonl'
        rows = [json.loads(line) for line in source.read_text().splitlines()]
        observed = phases(rows)
        if not any(item['case_id'] == case_id and item['source_sha256'] == sha(source)
                   for item in antecedent['cases']):
            raise ValueError('Source is not bound to selected antecedent proof')
        missing_stop = [dict(row) for row in rows]
        for i in range(140):
            missing_stop[i] = dict(missing_stop[i])
            missing_stop[i]['entrant'] = {**missing_stop[i]['entrant'], 'speed_mps': 1.0}
        try:
            phases(missing_stop)
        except ValueError:
            pass
        else:
            raise AssertionError('Missing prior stop accepted')
        missing_about = [dict(row) for row in rows]
        for i in range(140, 180):
            missing_about[i] = dict(missing_about[i])
            missing_about[i]['entrant'] = {**missing_about[i]['entrant'], 'speed_mps': 0.0}
        try:
            phases(missing_about)
        except ValueError:
            pass
        else:
            raise AssertionError('Missing about-to-enter phase accepted')
        if not reject(rows, 200, {'x_m': -12.0}):
            raise AssertionError('Missing crossing frame accepted')
        cases.append({'case_id': case_id, 'source_sha256': sha(source), **observed,
                      'negative_rejections': ['missing_prior_stop', 'missing_about_phase',
                                              'missing_crossing_frame']})
    receipt = {'format': 'c111294-branch-allocation-cpu-proof-v1', 'passed': True,
               'assignment_id': ASSIGNMENT, 'input_sha256': sha(Path('inputs') / ASSIGNMENT / 'assignment.json'),
               'case_plan_sha256': sha(HERE / 'case-plan.json'),
               'manifest_sha256': sha(manifest_path),
               'selected_antecedent_sha256': sha(antecedent_path),
               'cases': cases, 'conditional_prior_yield_requested': True,
               'lawful_prior_yield_verified': False, 'original_native_observed': False,
               'legal_verdict_claimed': False}
    path = HERE / 'branch-allocation-cpu-proof.json'
    path.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'passed': True, 'cases': len(cases), 'receipt_sha256': sha(path)}))


if __name__ == '__main__':
    main()
