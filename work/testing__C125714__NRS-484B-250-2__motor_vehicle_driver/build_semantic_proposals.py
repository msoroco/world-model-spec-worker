"""Rebuild draft canonical proposals for the C125714 CPU package."""
import copy
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PEER = ROOT.parent / 'testing__C125751__NRS-484B-250-2__motor_vehicle_driver' / 'proposals'
OUT = ROOT / 'proposals'
AID = ROOT.name


def read(path):
    return json.loads(path.read_text())


def write(name, value):
    path = OUT / name
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')
    return {'path': 'proposals/' + name, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    assignment = read(ROOT.parent.parent / 'inputs' / AID / 'assignment.json')
    manifest = read(ROOT / 'execution-manifest.json')
    existing_cases = {c['case_id']: c for c in read(OUT / 'cases.json')['cases']}
    template = read(PEER / 'template.json')
    relevance = read(PEER / 'relevance.json')
    relevance['cell_id'] = 'C125714'
    relevance['relevant_laws'][0]['relevance_type'] = 'median-opening vehicle entry and right-of-way qualification'
    relevance['relevant_laws'][0]['notes'] = (
        'The cell has a median opening and another vehicle. Original road, body-entry, '
        'approach, device and turn sources must establish whether both paths enter '
        'one statutory intersection from different highways and whether an exclusion applies.')
    refs = {'relevance_batch': write('relevance-batch.json', relevance),
            'relevance': write('relevance.json', relevance),
            'template': write('template.json', template)}

    judgments = []
    for i in range(1, 5):
        judgment = read(PEER / f'judgment-observables-{i}.json')
        req = judgment['observable_requirements']
        req['context_inputs'] = [{
            'name': 'entry_context', 'unit': 'structured record',
            'description': 'Saved source-hashed body entry, approach geometry, device inventory and turn context'}]
        req['recording_needs'] = [{
            'name': 'yield_control', 'unit': 'structured record',
            'description': 'Original per-frame controller state joined to body and route history'}]
        if i == 1:
            req['observables'] = [
                {'name': 'body_entry_time_delta_s', 'unit': 's',
                 'description': 'Signed original complete-body entry time difference'},
                {'name': 'other_approach_side', 'unit': 'structured record',
                 'description': 'Source-grounded right or left approach geometry'}]
        elif i == 2:
            req['observables'] = [
                {'name': 'ego_speed', 'unit': 'm/s', 'description': 'Original subject motion'},
                {'name': 'other_speed', 'unit': 'm/s', 'description': 'Original other vehicle motion'},
                {'name': 'yield_control_attempt', 'unit': 'structured record',
                 'description': 'Original controller hold and release context'}]
        elif i == 3:
            req['observables'] = [{
                'name': 'device_inventory', 'unit': 'structured record',
                'description': 'Sourced device presence, official status and governance review'}]
            req['sweep_dimensions'] = []
            req['limitations'] = [
                'The authored other-vehicle cell does not establish an officially controlled crossing; device applicability requires independent source review.']
        else:
            req['observables'] = [{
                'name': 'turn_context', 'unit': 'structured record',
                'description': 'Authored intention and original heading/body trajectory for the opposite approach'}]
        judgments.append(write(f'judgment-observables-{i}.json', judgment))
    refs['judgment_observables'] = judgments

    binding = read(PEER / 'bindings.json')
    binding['cell_id'] = 'C125714'
    binding['established_contexts'] = [
        'Median opening, travel maneuver and other-vehicle control are catalog attributes; '
        'statutory intersection identity, official devices and realized Native motion remain under source review.']
    binding['variable_parameters'] = [v for v in binding['variable_parameters']
                                      if v['name'] != 'native_signal_state']
    refs['bindings'] = write('bindings.json', binding)

    baseline_assignments = {
        'commanded_approach_speed': {'kind': 'controller', 'value': 5, 'unit': 'm/s'},
        'commanded_turn_path': {'kind': 'controller', 'value': 'travel_waypoints', 'unit': 'structured record'},
        'other_release_frame': {'kind': 'controller', 'value': 20, 'unit': 'frame'},
        'ego_speed': {'kind': 'subject_behavior', 'value': None, 'unit': 'm/s'},
        'body_entry_time_delta_s': {'kind': 'subject_behavior', 'value': None, 'unit': 's'},
        'official_device_status': {'kind': 'world_setup', 'value': 'unverified', 'unit': 'categorical'},
        'opposite_direction_left_turn': {'kind': 'world_setup', 'value': 'unverified', 'unit': 'categorical'},
    }
    descriptions = []
    for entry in manifest['cases']:
        descriptions.append(read(ROOT / entry['construction'])['recording_description'])
    baseline = {
        'case_id': AID + '__baseline', 'target_law_id': None, 'target_type': 'baseline',
        'rationale': 'Shared authored median-opening crossing reference; physical identity unverified',
        'variable_assignments': copy.deepcopy(baseline_assignments),
        'unresolved_judgment_calls': [], 'recording_description': descriptions[0]}
    cases = [baseline]
    phrases = [j['phrase'] for j in template['structure']['judgment_calls_needed']]
    for entry, description in zip(manifest['cases'], descriptions):
        case = copy.deepcopy(existing_cases[entry['case_id']])
        tail = entry['case_id'].split('__')[-1]
        assignments = copy.deepcopy(baseline_assignments)
        if tail.endswith('earlier'):
            assignments['other_release_frame']['value'] = 10
        elif tail.endswith('later'):
            assignments['other_release_frame']['value'] = 40
        if 'intends_left' in tail or 'makes_left' in tail:
            assignments['commanded_turn_path']['value'] = 'opposite_left_waypoints'
            assignments['opposite_direction_left_turn']['value'] = 'authored intention; realized motion unverified'
        case['variable_assignments'] = assignments
        case['recording_description'] = description
        case['target_type'] = 'boundary_probe'
        case['paired_probe_id'] = 'c125714-' + tail
        case['deliberate_differences'] = []
        case['probe'] = {
            'primary_variable': 'other_release_frame',
            'comparison_or_standard': 'original body-entry timing and approach/turn context; qualitative legal judgment unresolved',
            'target_value_or_branch': tail}
        case['unresolved_judgment_calls'] = phrases
        cases.append(case)
    sweep_specs = []
    for i, judgment in enumerate(template['structure']['judgment_calls_needed'], 1):
        spec = copy.deepcopy(read(PEER / 'cases.json')['sweep_specs'][i-1])
        spec['sweep_id'] = f'c125714-{i}'
        spec['variable_assignments'] = copy.deepcopy(baseline_assignments)
        spec['recording_description'] = descriptions[0]
        spec['rationale'] = 'Existing exact cases provide CPU source probes; a physical sweep requires site and motion verification.'
        spec['missing_inputs'] = ['verified Native motion, source geometry and physical sweep range for ' + judgment['phrase']]
        sweep_specs.append(spec)
    refs['cases'] = write('cases.json', {
        'cell_id': 'C125714', 'actor': assignment['actor'], 'status': 'draft',
        'cases': cases, 'sweep_specs': sweep_specs, 'sweeps_expanded': []})
    write('semantic-index.json', {'assignment_id': AID, 'format': 'worker-semantic-delivery', 'stages': refs})


if __name__ == '__main__':
    main()
