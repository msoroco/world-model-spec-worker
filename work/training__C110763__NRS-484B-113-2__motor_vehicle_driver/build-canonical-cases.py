"""Materialize the source-bound reverse endpoint pair for the canonical cases stage."""
import copy
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PROPOSALS = HERE / 'proposals'
ASSIGNMENT = 'training__C110763__NRS-484B-113-2__motor_vehicle_driver'
LAW = 'NRS-484B-113-2'


def load(name):
    return json.loads((PROPOSALS / name).read_text())


def save(name, value):
    (PROPOSALS / name).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


binding = load('bindings.json')
controller = {
    'name': 'reverse_stop_center_x_m',
    'kind': 'controller',
    'range_or_domain': 'authored 8 m or 10 m x-coordinate on the same approach; the original Native endpoint remains unknown',
    'used_by_laws': [LAW],
}
if not any(v['name'] == controller['name'] for v in binding['variable_parameters']):
    binding['variable_parameters'].append(controller)
save('bindings.json', binding)

previous = load('cases.json')
recording = copy.deepcopy(previous['cases'][0]['recording_description'])
if not any(item['name'] == 'source_camera_views' for item in recording['channels']):
    recording['channels'].append({
        'name': 'source_camera_views', 'unit': 'video', 'sampling_rate_hz': 20,
        'method': 'four original synchronized source-camera files and frame index; no synthetic frame substitutes for original capture',
        'time_window': '30 s / 600 joined frames', 'reference_frame': 'original Native and decoded video frame IDs',
        'uncertainty': 'one 50 ms sample; original pixels pending',
    })
for name, method in (
    ('intersection_geometry', 'surveyed original OpenDRIVE junction polygon and frame-joined body footprint'),
    ('crosswalk_geometry', 'surveyed original crosswalk polygon or verified absence on the selected road'),
    ('corner_geometry', 'surveyed original corner geometry and frame-joined vehicle path'),
):
    if not any(item['name'] == name for item in recording['context_inputs']):
        recording['context_inputs'].append({'name': name, 'unit': 'structured', 'method': method})

def assignments(stop):
    return {
        'reverse_motion': {'kind': 'subject_behavior', 'value': None, 'unit': 'm/s', 'source': 'original Native velocity and heading'},
        'intersection_boundary': {'kind': 'world_setup', 'value': [-7.0, -7.0, 7.0, 7.0], 'unit': 'm', 'source': 'authored OpenDRIVE junction; original survey pending'},
        'reverse_stop_center_x_m': {'kind': 'controller', 'value': stop, 'unit': 'm', 'source': 'authored reverse route stop target'},
    }

cases = [{
    'case_id': ASSIGNMENT + '__baseline', 'target_law_id': None,
    'target_type': 'baseline', 'rationale': 'Neutral shared setup definition; no simulated or observed baseline outcome.',
    'variable_assignments': assignments(10.0), 'recording_description': copy.deepcopy(recording),
    'unresolved_judgment_calls': [],
}]
for suffix, stop in [('probe_1', 10.0), ('probe_2', 8.0)]:
    cases.append({
        'case_id': ASSIGNMENT + '__' + suffix, 'target_law_id': LAW,
        'target_type': 'boundary_probe',
        'rationale': 'Compare fixed authored reverse endpoint requests on one surveyed approach; legal and original physical outcomes remain unresolved.',
        'paired_probe_id': ASSIGNMENT + '__reverse_endpoint_pair',
        'deliberate_differences': ['reverse_stop_center_x_m'],
        'probe': {'primary_variable': 'reverse_stop_center_x_m',
                  'comparison_or_standard': 'same-geometry reverse endpoint request, with original overlap to be measured',
                  'target_value_or_branch': stop},
        'variable_assignments': assignments(stop),
        'recording_description': copy.deepcopy(recording),
        'unresolved_judgment_calls': ['back into an intersection', 'on or over a crosswalk', 'around a street corner'],
    })

template = load('template.json')
sweeps = []
for index, judgment in enumerate(template['structure']['judgment_calls_needed'], 1):
    sweeps.append({
        'sweep_id': f'C110763-113-2-branch-{index}', 'target_law_id': LAW,
        'judgment_refs': [{'phrase': judgment['phrase'], 'note': judgment['note']}],
        'status': 'incomplete', 'rationale': 'Physical observation grid remains unselected pending source-grounded geometry and feasible controller range; no legal cutoff is assigned.',
        'missing_inputs': [
            'Surveyed original source geometry and original Native motion for this statutory branch',
            'Feasible physical sweep range and resolution grounded in the selected construction',
        ],
    })

save('cases.json', {
    'cell_id': 'C110763', 'actor': 'motor_vehicle_driver', 'status': 'draft',
    'cases': cases, 'sweep_specs': sweeps,
})
