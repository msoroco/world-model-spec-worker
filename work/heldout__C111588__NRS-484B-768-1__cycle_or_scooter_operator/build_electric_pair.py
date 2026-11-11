"""Author source-bound electric-device CPU diagnostics and exact fallbacks."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
BASE = 'heldout__C111588__NRS-484B-768-1__cycle_or_scooter_operator__bicycle_signal_once'
VIDEO_SHA = '4d5541f025afa64755261e4f4811e6b61617fd1cd22d0a62dc785fcf61a6d230'


def save(path, obj, compact=False):
    path.write_text(json.dumps(obj, separators=(',', ':') if compact else None,
                               indent=None if compact else 2, allow_nan=False) + '\n')


def sha(path):
    return sha256(path.read_bytes()).hexdigest()


def modify_runner(source, device):
    old = "        bicycle_blueprint = library.find('vehicle.bh.crossbike')\n        if bicycle_blueprint.get_attribute('base_type').as_str() != 'bicycle':\n            raise ValueError('Native selected actor is not a bicycle blueprint')"
    new = "        bicycle_blueprint, device_readback = select_device(library, '" + device + "')"
    assert old in source
    source = source.replace('from rider_route import control, select_left_turn',
        'from rider_route import control, select_left_turn\nfrom rider_device_class import select as select_device')
    source = source.replace(old, new)
    source = source.replace("        actors.append(bicycle)\n", "        actors.append(bicycle)\n        device_readback['actor_id'] = str(bicycle.id)\n        device_readback['actor_type_id'] = bicycle.type_id\n        (output / 'device_blueprint_readback.json').write_text(json.dumps(device_readback, indent=2) + '\\n')\n")
    source = source.replace("'device_type': 'bicycle',", "'device_type': '" + device + "',")
    source = source.replace("'device_type_source': 'Native vehicle.bh.crossbike blueprint base_type readback',",
                            "'device_type_source': 'Native candidate blueprint readback; device class and electric drive unverified',")
    source = source.replace("        frames = []", "        frames = []\n        frame_times = []")
    source = source.replace("            frames.append(frame)", "            frames.append(frame)\n            frame_times.append(time_s)")
    marker = '        cameras.verify(frames)\n'
    assert marker in source
    source = source.replace(marker, marker + "        for sink in sinks.values():\n            sink.close()\n        sinks.clear()\n        from hashlib import sha256\n        video_sha = sha256((output / 'driver_reference.mkv').read_bytes()).hexdigest()\n        (output / 'device_visual_review.jsonl').write_text(''.join(\n            json.dumps({'frame': frame, 'time_s': time_s, 'source_video_sha256': video_sha,\n                        'device_form_visible': None, 'rider_standing': None}) + '\\n'\n            for frame, time_s in zip(frames, frame_times)))\n")
    return source


def modify_finalizer(source, device):
    marker = "if __name__ == '__main__':\n    main()"
    extension = '''from rider_device_class import measure as _device_measure

def measure_electric_device(attempt):
    return _device_measure(attempt, 'DEVICE_TOKEN')

_base_analyze = analyze
def analyze(attempt):
    report = _base_analyze(attempt)
    observation = measure_electric_device(attempt)
    report['measurements']['electric_device_observation'] = {
        'method': 'measure_electric_device', 'value': observation,
        'sources': {**report['measurements']['rider_turn_signal_observation']['sources'],
                    **observation['sources']}}
    report['limitations'].append('Native blueprint and original pixel review do not yet confirm electric drive or device form.')
    return report

_base_build_result = build_result
def build_result(attempt, report):
    result = _base_build_result(attempt, report)
    observation = report['measurements']['electric_device_observation']['value']
    result['measured_values']['electric_device_observation'] = observation
    root = Path(attempt)
    channel = root / 'electric_device_observation.jsonl'
    if channel.exists():
        raise ValueError('Retain prior derived electric device channel')
    frames = [json.loads(line) for line in (root / 'device_visual_review.jsonl').read_text().splitlines() if line.strip()]
    channel.write_text(''.join(json.dumps({'frame': row['frame'], 'time_s': row['time_s'],
        'value': int(row['device_form_visible'] is True),
        'reviewed': row['device_form_visible'] is not None}) + '\\n' for row in frames))
    from hashlib import sha256
    result['recording_evidence'].append({'name': 'electric_device_observation', 'unit': 'category',
        'reference': 'electric_device_observation.jsonl',
        'sha256': sha256(channel.read_bytes()).hexdigest()})
    result['realized_observables']['electric_device_observation'] = {
        'unit': 'category', 'method': 'original pixel review joined to Native blueprint readback',
        'time_window': 'all original frames', 'statistic': 'device-form visible frames',
        'reference': 'electric_device_observation.jsonl',
        'value': sum(row['device_form_visible'] is True for row in frames),
        'sample_window_s': [frames[0]['time_s'], frames[-1]['time_s']]}
    result['physical_acceptance_claimed'] = False
    result['legal_acceptance_claimed'] = False
    return result

'''.replace('DEVICE_TOKEN', device)
    assert marker in source
    return source.replace(marker, extension + marker)


def modify_test(source, device):
    marker = '    for name, items in rows.items():\n'
    extra = "    (root / 'device_blueprint_readback.json').write_text(json.dumps({'blueprint_id': 'synthetic-electric-device', 'device_class_candidate': '" + device + "', 'device_class_confirmed': None, 'electric_drive_verified': None}) + '\\n')\n    rows['device_visual_review.jsonl'] = [{'frame': i, 'time_s': i * .05, 'source_video_sha256': video_sha, 'device_form_visible': None, 'rider_standing': None} for i in range(4)]\n"
    assert marker in source
    source = source.replace(marker, extra + marker)
    source = source.replace("'device_type': 'bicycle'", "'device_type': '" + device + "'")
    return source


def build():
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    proposal = json.loads((ROOT / 'proposals/cases.json').read_text())
    for offset, device in enumerate(('electric_bicycle', 'electric_scooter')):
        slug = device + '_signal_once'
        case = BASE.replace('bicycle_signal_once', slug)
        folder = ROOT / 'cases' / slug
        folder.mkdir(exist_ok=True)
        requirement = device.replace('_', ' ') + ' roadway direct-course turn with one observed pre-turn arm signal and source-reviewed device identity'
        for number in (0, 1, 2, 3):
            src = ROOT / ('first-construction.json' if number == 0 else f'cases/bicycle_signal_once/fallback{number}-construction.json')
            obj = json.loads(json.dumps(json.loads(src.read_text())).replace(BASE, case))
            obj['case_id'] = case
            obj['recording_description']['channels'].append({'name': 'electric_device_observation', 'unit': 'category', 'method': 'Native actor blueprint readback joined to original source-video form review', 'sampling_rate_hz': 20, 'time_window': 'all original frames', 'reference_frame': 'Native actor and driver_reference video', 'uncertainty': 'candidate class and synthetic diagnostic cannot prove electric drive or device form'})
            obj['recording_description']['limitations'].append('Native device class and electric propulsion require source review; synthetic diagnostic makes no physical claim.')
            files = {row['path']: row for row in obj['files']}
            for name in ('config.json', 'probe-config.json'):
                config = json.loads(files[name]['content'])
                config['device_class_candidate'] = device
                config['case']['recording_description'] = obj['recording_description']
                files[name]['content'] = json.dumps(config, indent=2) + '\n'
            for name in ('native_rider_probe.py', 'runner.py'):
                files[name]['content'] = modify_runner(files[name]['content'], device)
            files['rider_signal_finalizer.py']['content'] = modify_finalizer(files['rider_signal_finalizer.py']['content'], device)
            files['tests/test_rider_signal_finalizer.py']['content'] = modify_test(files['tests/test_rider_signal_finalizer.py']['content'], device)
            obj['files'].append({'path': 'rider_device_class.py', 'content': (ROOT / 'rider_device_class.py').read_text()})
            save(folder / ('construction.json' if number == 0 else f'fallback{number}-construction.json'), obj)
        diagnostic = json.loads(json.dumps(json.loads((ROOT / 'diagnostic-input.json').read_text())).replace(BASE, case))
        context = json.loads(diagnostic['files']['rider_context.json'])
        context['device_type'] = device
        context['device_type_source'] = 'synthetic diagnostic device-class candidate; no Native identity or electric drive asserted'
        diagnostic['files']['rider_context.json'] = json.dumps(context, indent=2) + '\n'
        diagnostic['files']['device_blueprint_readback.json'] = json.dumps({'blueprint_id': 'synthetic-electric-device', 'attributes': {}, 'selection_query': 'diagnostic only', 'device_class_candidate': device, 'device_class_confirmed': None, 'electric_drive_verified': None}, indent=2) + '\n'
        frames = [json.loads(line) for line in diagnostic['files']['video_frames.jsonl'].splitlines() if line.strip()]
        diagnostic['files']['device_visual_review.jsonl'] = ''.join(json.dumps({'frame': frame['carla_frame'], 'time_s': frame['time_s'], 'source_video_sha256': VIDEO_SHA, 'device_form_visible': None, 'rider_standing': None}) + '\n' for frame in frames)
        save(folder / 'diagnostic-input.json', diagnostic, compact=True)
        source_path = str((folder / 'diagnostic-input.json').relative_to(REPO))
        save(folder / 'diagnostic-recipe.json', {'format': 'worker-fixture-recipe', 'sources': [{'path': 'diagnostic-input.json', 'source': source_path, 'sha256': sha(folder / 'diagnostic-input.json')}], 'generator': {'source': source_path, 'sha256': sha(folder / 'diagnostic-input.json')}})
        contract = json.loads(json.dumps(json.loads((ROOT / 'first-measurement-contract.json').read_text())).replace(BASE, case))
        contract['requirements'][0].update({'disposition_index': 7 + offset, 'requirement': requirement, 'output_key': 'electric_device_observation', 'method': 'measure_electric_device'})
        contract['requirements'][0]['inputs'] += ['device_blueprint_readback.json', 'device_visual_review.jsonl']
        contract['negative'] = {'remove': ['device_blueprint_readback.json'], 'error_contains': 'Missing required source: device_blueprint_readback.json'}
        save(folder / 'measurement-contract.json', contract)
        manifest = json.loads((ROOT / 'first-execution-manifest.json').read_text())
        entry = manifest['cases'][0]
        entry['case_id'] = case
        entry['construction'] = f'cases/{slug}/construction.json'
        entry['construction_sha256'] = sha(folder / 'construction.json')
        entry['measurement_contract'] = f'cases/{slug}/measurement-contract.json'
        entry['fixture_recipe'] = f'{source_path[:-len("diagnostic-input.json")]}diagnostic-recipe.json'
        entry.pop('physical_preparation', None)
        entry['candidate_risk'] = {'status': 'physical', 'reason': 'Native electric device asset, rider form, arm visibility and motion remain unverified'}
        for number, candidate in enumerate(entry['candidates'], 1):
            candidate['construction'] = f'cases/{slug}/fallback{number}-construction.json'
            candidate['construction_sha256'] = sha(folder / f'fallback{number}-construction.json')
            candidate.pop('offline', None)
            candidate.pop('compatibility', None)
        save(ROOT / (device.replace('_', '-') + '-manifest.json'), manifest)
        next(x for x in plan['cases'] if x['case_id'] == case)['construction_status'] = 'primary_and_three_fallbacks_authored_cpu_proofs_pending_physical_unverified'
        plan['requirement_dispositions'] = [row for row in plan['requirement_dispositions'] if case not in row['case_ids']]
        plan['requirement_dispositions'].append({'requirement': requirement, 'source': 'inputs/heldout__C111588__NRS-484B-768-1__cycle_or_scooter_operator/assignment.json', 'status': 'selected_required', 'case_ids': [case], 'reason': 'source-bound electric-device software diagnostic; Native asset and physical/legal confirmation unresolved', 'evidence_or_gap': 'Synthetic black pixels and candidate blueprint tokens do not prove electric drive or device form.'})
        proposal['cases'] = [row for row in proposal['cases'] if row['case_id'] != case]
        clone = json.loads(json.dumps(next(x for x in proposal['cases'] if x['case_id'] == BASE)))
        clone['case_id'] = case
        clone['rationale'] = 'Source-bound electric-device class diagnostic; physical class and visibility remain open'
        clone['variable_assignments']['rider_device_class'] = {'kind': 'environment', 'value': device}
        clone['variable_assignments']['device_blueprint_choice'] = {'kind': 'controller', 'value': 'source-bound-' + device + '-selector'}
        clone['recording_description'] = json.loads((folder / 'construction.json').read_text())['recording_description']
        clone['paired_probe_id'] = device
        clone['deliberate_differences'] = ['rider_device_class', 'device_blueprint_choice']
        clone['probe'] = {'primary_variable': 'rider_device_class', 'comparison_or_standard': 'bicycle signal once versus electric device signal once', 'target_value_or_branch': device}
        proposal['cases'].append(clone)
        print(case)
    save(ROOT / 'case-plan.json', plan)
    save(ROOT / 'proposals/cases.json', proposal)

if __name__ == '__main__':
    build()
