"""Build an exact safety-only turn with neither conditional signal triggered."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OLD = ROOT.name + '__pedestrian_no_horn_before_turn'
NEW = ROOT.name + '__safety_only_distant_users'
STEM = 'safety-only-distant'


def save(path, value, compact=False):
    path.write_text(json.dumps(value, separators=(',', ':') if compact else None,
                               indent=None if compact else 2) + '\n')
    return sha256(path.read_bytes()).hexdigest()


def construction(source, target, left_m=14., pcm_rate=None, overview_source=None):
    data = json.loads((ROOT / source).read_text().replace(OLD, NEW))
    for item in data['files']:
        item.pop('source', None)
        if item['path'] == 'runner.py':
            runner = item['content']
            runner = runner.replace('from turn_native_route import select_left_turn, route_targets, control_step',
                                    'from turn_native_route import select_left_turn, route_targets, control_step, participant_spawn_transform')
            old = "ped_location = scene['approach'][0].transform.location + carla.Location(x=6, y=2, z=.5)"
            if old not in runner:
                raise ValueError('No-horn construction geometry changed')
            runner = runner.replace(old, "ped_transform = participant_spawn_transform(carla, scene['approach'][0], along_m=6., left_m=" + str(left_m) + ")")
            runner = runner.replace("carla.Transform(ped_location, scene['approach'][0].transform.rotation)",
                                    'ped_transform')
            runner = runner.replace("'pedestrian_may_be_affected': True", "'pedestrian_may_be_affected': False")
            runner = runner.replace('Native pedestrian near selected connected left-turn corridor',
                                    'Native pedestrian placed left of route; original body/effect review required')
            if pcm_rate:
                runner = runner.replace('device=require_microphone_device())',
                                        'device=require_microphone_device(), sample_rate_hz=' + str(pcm_rate) + ')')
            item['content'] = runner
        elif item['path'] == 'turn_native_route.py':
            item['content'] = (ROOT / 'native_horn/turn_native_route.py').read_text()
        elif item['path'] == 'turn_camera_capture.py' and overview_source:
            fallback = json.loads((ROOT / overview_source).read_text())
            item['content'] = next(x['content'] for x in fallback['files']
                                   if x['path'] == 'turn_camera_capture.py')
    return save(ROOT / target, data)


def build():
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    old = next(x for x in manifest['cases'] if x['case_id'] == OLD)
    name = STEM + '-construction.json'
    construction_hash = construction(old['construction'], name)
    diagnostic = json.loads((ROOT / 'pedestrian-no-horn-diagnostic.json').read_text())
    files = diagnostic['files']
    rows = [json.loads(line) for line in files['participant_bodies.jsonl'].splitlines() if line]
    for row in rows:
        row['bodies']['ped_listener']['y_m'] += 12.
    files['participant_bodies.jsonl'] = ''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows)
    context = json.loads(files['affected_participants.json'])
    context['pedestrian_may_be_affected'] = False
    context['pedestrian_may_be_affected_source'] = ('diagnostic original pedestrian body offset left of the route; '
                                                     'actual effect remains unverified')
    files['affected_participants.json'] = json.dumps(context) + '\n'
    diagnostic_name = STEM + '-diagnostic.json'
    diagnostic_hash = save(ROOT / diagnostic_name, diagnostic, compact=True)
    recipe = json.loads((ROOT / 'pedestrian-no-horn-recipe.json').read_text().replace(OLD, NEW))
    for ref in recipe['sources']:
        ref['source'] = 'work/' + ROOT.name + '/' + diagnostic_name
        ref['sha256'] = diagnostic_hash
    recipe['generator']['source'] = 'work/' + ROOT.name + '/' + diagnostic_name
    recipe['generator']['sha256'] = diagnostic_hash
    recipe_name = STEM + '-recipe.json'
    save(ROOT / recipe_name, recipe)
    contract_name = STEM + '-measurement-contract.json'
    save(ROOT / contract_name, json.loads((ROOT / old['measurement_contract']).read_text().replace(OLD, NEW)))
    entry = {key: json.loads(json.dumps(value)) for key, value in old.items()
             if key in ('kind', 'measurement_procedure', 'acquisition', 'candidate_risk')}
    entry.update(case_id=NEW, construction=name, construction_sha256=construction_hash,
                 measurement_contract=contract_name,
                 fixture_recipe='work/' + ROOT.name + '/' + recipe_name, candidates=[])
    entry['candidate_risk'] = {'status': 'physical',
        'reason': 'A distant pedestrian may still intersect the turn or fall outside the original camera view.'}
    old_fallback3 = next(x for x in old['candidates'] if x['id'] == 'fallback3')
    candidates = [
        ('fallback1', 17., None, None,
         {'source': 'original Native participant bodies and turn route',
          'metric': 'minimum pedestrian-route clearance',
          'failure_condition': 'Primary distant placement still intersects the turn corridor'},
         ['pedestrian approach-relative left offset 14 to 17 m']),
        ('fallback2', 14., 32000, None,
         {'source': 'original listener microphone PCM', 'metric': '20 Hz audio packet continuity',
          'failure_condition': 'Primary listener device loses or misaligns a source packet'},
         ['listener PCM rate 16000 to 32000 Hz']),
        ('fallback3', 14., None, old_fallback3['construction'],
         {'source': 'original overview RGB decode', 'metric': 'distant pedestrian visible pixel count',
          'failure_condition': 'Primary overview crops the distant pedestrian'},
         ['overview camera mount x -8 to -9 m'])]
    for ident, left, rate, camera, trigger, knobs in candidates:
        candidate_name = STEM + '-' + ident + '-construction.json'
        digest = construction(old['construction'], candidate_name, left, rate, camera)
        entry['candidates'].append({'id': ident, 'construction': candidate_name,
                                    'construction_sha256': digest, 'trigger': trigger,
                                    'changed_knobs': knobs})
    manifest['cases'] = [x for x in manifest['cases'] if x['case_id'] != NEW] + [entry]
    save(manifest_path, manifest)
    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    variant = json.loads(json.dumps(next(x for x in plan['cases'] if x['case_id'] == OLD)).replace(OLD, NEW))
    variant['purpose'] = ('Measure the unchanged turn and safety observations with a pedestrian distant '
                          'from the selected route and neither conditional signal requested; actual effect is unjudged.')
    variant['construction_state'] = 'primary_pending_cpu_proofs'
    plan['cases'] = [x for x in plan['cases'] if x['case_id'] != NEW] + [variant]
    plan['comparisons'] = [x for x in plan['comparisons'] if x['comparison_id'] != 'safety_only_condition']
    plan['comparisons'].append({'comparison_id': 'safety_only_condition', 'case_ids': [OLD, NEW],
        'fixed_conditions': ['same selected direct-course turn, driver, vehicle, no horn or indicator, 20 Hz duration and four cameras'],
        'deliberate_differences': ['pedestrian route-side placement 2 m versus 14 m; sourced potential-effect context changes while legal effect remains unjudged']})
    for item in plan['requirement_dispositions']:
        if item['status'] == 'selected_required' and NEW not in item['case_ids']:
            item['case_ids'].append(NEW)
    save(plan_path, plan)
    proposals_path = ROOT / 'proposals/cases.json'
    proposals = json.loads(proposals_path.read_text())
    proposal = json.loads(json.dumps(next(x for x in proposals['cases'] if x['case_id'] == OLD)).replace(OLD, NEW))
    proposals['cases'] = [x for x in proposals['cases'] if x['case_id'] != NEW] + [proposal]
    save(proposals_path, proposals)
    index_path = ROOT / 'proposals/semantic-index.json'
    index = json.loads(index_path.read_text())
    index['stages']['cases']['sha256'] = sha256(proposals_path.read_bytes()).hexdigest()
    save(index_path, index)
    return NEW, construction_hash, diagnostic_hash


if __name__ == '__main__':
    print(build())
