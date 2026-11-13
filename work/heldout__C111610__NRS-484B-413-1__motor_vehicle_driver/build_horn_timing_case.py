"""Construct a later horn request with original-shaped listener samples."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OLD = ROOT.name + '__pedestrian_horn_before_turn'
NEW = ROOT.name + '__pedestrian_horn_after_onset'
STEM = 'pedestrian-horn-late'


def save(path, value, compact=False):
    path.write_text(json.dumps(value, separators=(',', ':') if compact else None,
                               indent=None if compact else 2) + '\n')
    return sha256(path.read_bytes()).hexdigest()


def build():
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    original = next(case for case in manifest['cases'] if case['case_id'] == OLD)
    def construction(source_name, target_name, candidate='primary'):
        source = json.loads((ROOT / source_name).read_text().replace(OLD, NEW))
        for item in source['files']:
            if item['path'] == 'runner.py':
                runner = (ROOT / 'native_horn/runner.py').read_text().replace(OLD, NEW)
                if candidate == 'fallback2':
                    runner = runner.replace('device=require_microphone_device())',
                                            'device=require_microphone_device(), sample_rate_hz=32000)')
                item['content'] = runner
            elif item['path'] == 'turn_native_route.py':
                item['content'] = (ROOT / 'native_horn/turn_native_route.py').read_text()
            elif item['path'] == 'config.json':
                config = json.loads(item['content'])
                config['engineering']['horn_request_frame'] = 120
                if candidate == 'fallback1':
                    config['engineering']['pedestrian_along_m'] = 5.0
                    config['engineering']['pedestrian_left_m'] = 1.5
                item['content'] = json.dumps(config, indent=2) + '\n'
        return save(ROOT / target_name, source)
    construction_name = STEM + '-construction.json'
    construction_hash = construction(original['construction'], construction_name)

    diagnostic = json.loads((ROOT / 'pedestrian-horn-diagnostic.json').read_text())
    files = diagnostic['files']
    pcm = [json.loads(line) for line in files['listener_audio_original.jsonl'].splitlines()]
    signals = [json.loads(line) for line in files['ego_signal_audio.jsonl'].splitlines()]
    first = signals[0]['frame']
    for index, (packet, signal) in enumerate(zip(pcm, signals)):
        samples = [0.5] * 8 if index >= 7 else [0.0] * 8
        digest = sha256(json.dumps(samples, separators=(',', ':')).encode()).hexdigest()
        packet['samples'] = samples
        packet['sha256'] = digest
        signal['listener_audio_samples'] = samples
        signal['listener_packet_sha256'] = digest
    files['listener_audio_original.jsonl'] = ''.join(json.dumps(row) + '\n' for row in pcm)
    files['ego_signal_audio.jsonl'] = ''.join(json.dumps(row) + '\n' for row in signals)
    actuation = json.loads(files['horn_actuation.jsonl'].strip())
    actuation['request']['frame'] = first + 7
    actuation['request']['native_time_s'] = signals[7]['time_s']
    actuation['acknowledgement']['frame'] = first + 7
    files['horn_actuation.jsonl'] = json.dumps(actuation) + '\n'
    diagnostic_name = STEM + '-diagnostic.json'
    diagnostic_hash = save(ROOT / diagnostic_name, diagnostic, compact=True)
    recipe = json.loads((ROOT / 'pedestrian-horn-recipe.json').read_text().replace(OLD, NEW))
    for ref in recipe['sources']:
        ref['source'] = 'work/' + ROOT.name + '/' + diagnostic_name
        ref['sha256'] = diagnostic_hash
    recipe['generator']['source'] = 'work/' + ROOT.name + '/' + diagnostic_name
    recipe['generator']['sha256'] = diagnostic_hash
    recipe_name = STEM + '-recipe.json'
    save(ROOT / recipe_name, recipe)
    contract_name = STEM + '-measurement-contract.json'
    save(ROOT / contract_name, json.loads((ROOT / original['measurement_contract']).read_text().replace(OLD, NEW)))
    entry = {key: json.loads(json.dumps(value)) for key, value in original.items()
             if key in ('kind', 'measurement_procedure', 'acquisition', 'candidate_risk')}
    entry.update(case_id=NEW, construction=construction_name,
                 construction_sha256=construction_hash, measurement_contract=contract_name,
                 fixture_recipe='work/' + ROOT.name + '/' + recipe_name, candidates=[])
    for old in original['candidates']:
        name = STEM + '-' + old['id'] + '-construction.json'
        entry['candidates'].append({'id': old['id'], 'construction': name,
                                    'construction_sha256': construction(old['construction'], name, old['id']),
                                    'trigger': old['trigger'], 'changed_knobs': old['changed_knobs']})
    previous = next((case for case in manifest['cases'] if case['case_id'] == NEW), None)
    if previous and previous.get('construction_sha256') == construction_hash:
        for field in ('offline', 'compatibility', 'negative', 'saved_processing',
                      'delivery_acceptance', 'post_capture', 'physical_preparation'):
            if field in previous:
                entry[field] = previous[field]
        previous_candidates = {item['id']: item for item in previous['candidates']}
        for candidate in entry['candidates']:
            old = previous_candidates.get(candidate['id'])
            if old and old.get('construction_sha256') == candidate['construction_sha256']:
                for field in ('offline', 'compatibility'):
                    if field in old:
                        candidate[field] = old[field]
    manifest['cases'] = [case for case in manifest['cases'] if case['case_id'] != NEW] + [entry]
    save(manifest_path, manifest)

    plan_path = ROOT / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    previous_case = next((item for item in plan['cases'] if item['case_id'] == NEW), None)
    variant = json.loads(json.dumps(next(case for case in plan['cases'] if case['case_id'] == OLD)).replace(OLD, NEW))
    variant['purpose'] = ('Request the horn after the diagnostic turn onset while holding the pedestrian path, '
                          'turn and cameras fixed; compare measured timing without a legal audibility finding.')
    variant['construction_state'] = (previous_case or {}).get('construction_state', 'primary_pending_cpu_proofs')
    plan['cases'] = [case for case in plan['cases'] if case['case_id'] != NEW] + [variant]
    previous_comparison = next((item for item in plan['comparisons']
                                if item['comparison_id'] == 'horn_request_timing_sweep'), None)
    plan['comparisons'] = [item for item in plan['comparisons'] if item['comparison_id'] != 'horn_request_timing_sweep']
    comparison = {'comparison_id': 'horn_request_timing_sweep',
        'case_ids': [OLD, NEW],
        'fixed_conditions': ['same turn route, pedestrian body path, horn relay, 20 Hz duration and four cameras'],
        'deliberate_differences': ['horn request at Native frame 20 versus frame 120 in the late construction; '
                                  'diagnostic actuation at source frame 38035 versus 38040']}
    if previous_comparison:
        for key in ('audit_script', 'audit_script_sha256', 'audit_log', 'audit_log_sha256'):
            if key in previous_comparison:
                comparison[key] = previous_comparison[key]
    plan['comparisons'].append(comparison)
    for item in plan['requirement_dispositions']:
        if item['status'] == 'selected_required' and NEW not in item['case_ids']:
            item['case_ids'].append(NEW)
    save(plan_path, plan)
    proposal_path = ROOT / 'proposals/cases.json'
    proposals = json.loads(proposal_path.read_text())
    proposal = json.loads(json.dumps(next(item for item in proposals['cases'] if item['case_id'] == OLD)).replace(OLD, NEW))
    proposals['cases'] = [item for item in proposals['cases'] if item['case_id'] != NEW] + [proposal]
    save(proposal_path, proposals)
    index_path = ROOT / 'proposals/semantic-index.json'
    index = json.loads(index_path.read_text())
    index['stages']['cases']['sha256'] = sha256(proposal_path.read_bytes()).hexdigest()
    save(index_path, index)
    return NEW, construction_hash, diagnostic_hash


if __name__ == '__main__':
    print(build())
