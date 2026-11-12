"""Build a controlled farther-vehicle clearance case from the proved near case."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name
NEAR = ASSIGNMENT + '__vehicle_clearance_near_before_turn'
FAR = ASSIGNMENT + '__vehicle_clearance_far_before_turn'


def write(path, value, compact=False):
    path.write_text(json.dumps(value, separators=(',', ':') if compact else None,
                               indent=None if compact else 2) + '\n')
    return sha256(path.read_bytes()).hexdigest()


def construction(source, target, left_m):
    value = json.loads((ROOT / source).read_text().replace(NEAR, FAR))
    files = {item['path']: item for item in value['files']}
    config = json.loads(files['config.json']['content'])
    config['engineering']['vehicle_left_m'] = left_m
    files['config.json']['content'] = json.dumps(config, indent=2) + '\n'
    path = ROOT / target
    return write(path, value)


def build():
    left_m = 14.0
    primary_name = 'vehicle-clearance-far-construction.json'
    primary_hash = construction('vehicle-clearance-near-construction.json', primary_name, left_m)

    diagnostic = json.loads((ROOT / 'vehicle-clearance-near-diagnostic.json').read_text().replace(NEAR, FAR))
    rows = [json.loads(line) for line in diagnostic['files']['participant_bodies.jsonl'].splitlines() if line]
    for row in rows:
        row['bodies']['affected_vehicle']['y_m'] = 14.0
    diagnostic['files']['participant_bodies.jsonl'] = ''.join(json.dumps(row) + '\n' for row in rows)
    diagnostic_name = 'vehicle-clearance-far-diagnostic.json'
    diagnostic_hash = write(ROOT / diagnostic_name, diagnostic, compact=True)
    recipe = json.loads((ROOT / 'vehicle-clearance-near-recipe.json').read_text()
                        .replace('vehicle-clearance-near-diagnostic.json', diagnostic_name))
    for source in recipe['sources']:
        source['sha256'] = diagnostic_hash
    recipe['generator']['sha256'] = diagnostic_hash
    write(ROOT / 'vehicle-clearance-far-recipe.json', recipe)
    contract = json.loads((ROOT / 'vehicle-clearance-near-measurement-contract.json').read_text().replace(NEAR, FAR))
    write(ROOT / 'vehicle-clearance-far-measurement-contract.json', contract)

    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    near = next(item for item in manifest['cases'] if item['case_id'] == NEAR)
    far = {'case_id': FAR, 'kind': 'delivery', 'construction': primary_name,
           'construction_sha256': primary_hash,
           'measurement_procedure': {'entrypoint': 'turn_finalizer.py'},
           'measurement_contract': 'vehicle-clearance-far-measurement-contract.json',
           'fixture_recipe': f'work/{ASSIGNMENT}/vehicle-clearance-far-recipe.json',
           'candidate_risk': {'status': 'physical',
                              'reason': 'Farther vehicle placement and image visibility require original Native verification.'},
           'candidates': []}
    for candidate in near['candidates']:
        ident = candidate['id']
        name = f'vehicle-clearance-far-{ident}-construction.json'
        digest = construction(candidate['construction'], name, left_m)
        far['candidates'].append({'id': ident, 'construction': name,
                                  'construction_sha256': digest,
                                  'trigger': candidate['trigger'],
                                  'changed_knobs': candidate['changed_knobs']})
    manifest['cases'] = [item for item in manifest['cases'] if item['case_id'] != FAR] + [far]
    write(manifest_path, manifest)

    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    if FAR not in {item['case_id'] for item in plan['cases']}:
        new = json.loads(json.dumps(next(item for item in plan['cases'] if item['case_id'] == NEAR)).replace(NEAR, FAR))
        new['purpose'] = 'Measure original vehicle clearance after a 12 m lateral offset from the near placement; affectedness and reasonable safety remain unjudged.'
        new['construction_state'] = 'primary_construction_pending_cpu_proofs'
        plan['cases'].append(new)
        plan['comparisons'].append({'comparison_id': 'vehicle_clearance_sweep',
            'case_ids': [NEAR, FAR],
            'fixed_conditions': ['same selected turn, vehicle, indicator protocol, controller, 20 Hz duration and four cameras'],
            'deliberate_differences': ['constructed affected-vehicle left offset: 2 m versus 14 m']})
    for item in plan['requirement_dispositions']:
        if item['status'] == 'selected_required' and FAR not in item['case_ids']:
            item['case_ids'].append(FAR)
    write(plan_path, plan)
    proposal_path = ROOT / 'proposals/cases.json'
    proposals = json.loads(proposal_path.read_text())
    if FAR not in {item['case_id'] for item in proposals['cases']}:
        template = next(item for item in proposals['cases'] if item['case_id'] == NEAR)
        proposals['cases'].append(json.loads(json.dumps(template).replace(NEAR, FAR)))
        write(proposal_path, proposals)
    return {'case_id': FAR, 'construction_sha256': primary_hash,
            'diagnostic_sha256': diagnostic_hash}


if __name__ == '__main__':
    print(build())
