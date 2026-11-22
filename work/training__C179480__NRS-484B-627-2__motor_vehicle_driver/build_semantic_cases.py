"""Bind the four source-visible C179480 drafts into canonical draft stages."""
import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path

from audit_control_cell import inspect_inventory
from source_measurement import analyze_control, load_rows

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'runtime' / 'pipeline'))
from scenario_pipeline.batch_pipeline.sweeps import expand_sweeps

HERE = Path(__file__).resolve().parent
PROPOSALS = HERE / 'proposals'
CASES = ('reference', 'contrast', 'safe_operation_stop', 'law_required_stop')
VARIABLES = ('roadway_stop_placement', 'other_vehicle_hazard',
             'governing_stop_control', 'ego_stop_controller',
             'following_vehicle_controller', 'following_gap_m',
             'hazard_center_gap_m', 'governing_red_onset_s')


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def assignments(name, binding):
    values = {
        'roadway_stop_placement': 'shoulder_clear' if name == 'contrast' else 'travel_lane_overlap',
        'other_vehicle_hazard': 'designated_source_visible_hazard' if name == 'safe_operation_stop' else 'no_hazard_designated; scoped inventory retained',
        'governing_stop_control': 'designated_surveyed_red_light' if name == 'law_required_stop' else 'no_governing_control_designated; scoped inventory retained',
        'ego_stop_controller': 'source_measured_complete_stop_request',
        'following_vehicle_controller': 'fixed_approach_and_gap_response',
        'following_gap_m': 9.5,
        'hazard_center_gap_m': 8.0,
        'governing_red_onset_s': 11.0,
    }
    kinds = {item['name']: item['kind'] for item in binding['variable_parameters']}
    if set(values) != set(kinds) or set(values) != set(VARIABLES):
        raise ValueError('Canonical variable inventory differs from binding')
    return {key: {'kind': kinds[key], 'value': value} for key, value in values.items()}


def build():
    # The red control is supplemental: the frozen cell still requires a
    # source-visible other vehicle throughout this proposed case.
    law_source = HERE/'fixtures/law_required_stop-sources'
    light_id = read(law_source/'native-map-readback.json')['surveyed_governing_traffic_light_id']
    actor_source = law_source/'native-actors.jsonl'
    frame_map = law_source/'video_frames.jsonl'
    inspect_inventory(load_rows(actor_source, frame_map), light_id)
    control = analyze_control(actor_source, frame_map,
                              expected_control_id=light_id,
                              source_kind='synthetic_native_sample')
    if not control['associated_red_frames']:
        raise ValueError('Law-required draft has no source-associated red frames')
    binding = read(PROPOSALS/'bindings.json')
    template = read(PROPOSALS/'template.json')
    draft = read(PROPOSALS/'cases.json')
    old = {case['case_id'].rsplit('__', 1)[-1]: case for case in draft['cases']}
    if set(old) != set(CASES):
        raise ValueError('Four draft cases required')
    entries = []
    baseline = {
        'case_id': HERE.name+'__baseline', 'target_law_id': None,
        'target_type': 'baseline',
        'rationale': 'Shared definition only; no baseline recording or legal label selected.',
        'variable_assignments': assignments('reference', binding),
        'recording_description': old['reference']['recording_description'],
        'unresolved_judgment_calls': [],
    }
    entries.append(baseline)
    differences = {
        'reference': [], 'contrast': ['roadway_stop_placement'],
        'safe_operation_stop': ['other_vehicle_hazard'],
        'law_required_stop': ['governing_stop_control'],
    }
    probes = {
        'reference': ('roadway_stop_placement', 'travel_lane_overlap'),
        'contrast': ('roadway_stop_placement', 'shoulder_clear'),
        'safe_operation_stop': ('other_vehicle_hazard', 'designated_source_visible_hazard'),
        'law_required_stop': ('governing_stop_control', 'designated_surveyed_red_light'),
    }
    for name in CASES:
        source = old[name]
        variable, target = probes[name]
        entries.append({
            'case_id': source['case_id'], 'target_law_id': template['law_id'],
            'target_type': 'judgment_sweep',
            'rationale': source['case_description']+' Original traffic, necessity and compliance judgments remain unresolved.',
            'paired_probe_id': 'c179480-roadway-stop-factored',
            'deliberate_differences': differences[name],
            'probe': {'primary_variable': variable,
                      'comparison_or_standard': 'source-bound physical observation; no legal cutoff',
                      'target_value_or_branch': target},
            'variable_assignments': assignments(name, binding),
            'recording_description': source['recording_description'],
            'unresolved_judgment_calls': [item['phrase'] for item in
                                          template['structure']['judgment_calls_needed']],
        })
    specs = []
    for item in template['structure']['judgment_calls_needed']:
        slug = {'normal and reasonable movement of traffic': 'traffic-effect',
                'necessary for safe operation': 'safe-operation',
                'in compliance with law': 'governing-law'}[item['phrase']]
        spec = {
            'sweep_id': 'c179480-'+slug+'-pending',
            'target_law_id': template['law_id'],
            'judgment_refs': [item],
            'rationale': 'Qualitative statutory judgment requires original source and independent review, with no invented numeric cutoff.',
            'status': 'incomplete',
            'missing_inputs': [
                'Source-reviewed physical sampling range and comparison isolation',
                'Selected additional cases if original evidence leaves this judgment uncovered',
            ],
        }
        if slug == 'traffic-effect':
            # These settings are supported only by the synthetic CPU
            # source/measurement probe. Actual Native realization remains a
            # separate selected-case proof requirement.
            probe = read(HERE/'traffic-effect-sweep-probe.json')
            settings = [row['brake_gap_setting_m'] for row in probe['probe_rows']]
            if not probe['passed'] or settings != [7.0, 9.5, 12.0] or probe['original_native_observed']:
                raise ValueError('Traffic sweep engineering probe changed')
            recording = deepcopy(old['reference']['recording_description'])
            recording['channels'].append({
                'name': 'following_gap_m', 'unit': 'm',
                'method': 'derive each ego-minus-follower longitudinal gap from original Native actor rows; report minimum in the stop window',
                'sampling_rate_hz': 20, 'time_window': 'all 600 frames / 30 seconds',
                'reference_frame': 'original CARLA frame joined to four video sources',
                'uncertainty': '50 ms sampling; controller target may differ from realized minimum; original Native capture required',
            })
            spec = {
                'sweep_id': 'c179480-traffic-effect-gap',
                'target_law_id': template['law_id'],
                'judgment_refs': [item],
                'rationale': 'Sample follower brake-gap engineering settings while holding roadway-stop placement, ego stop and non-axis setup fixed; preserve raw traffic history for independent judgment.',
                'status': 'complete', 'mode': 'one_dimensional',
                'axes': [{
                    'variable': 'following_gap_m', 'observable': 'following_gap_m', 'unit': 'm',
                    'min': 7.0, 'max': 12.0, 'spacing': 2.5,
                    'measurement': {
                        'method': 'derive longitudinal gap from original ego and follower actor positions on each synchronized CARLA frame',
                        'time_window': 'all 600 frames / 30 seconds including the complete roadway stop',
                        'statistic': 'min',
                    },
                    'range_rationale': 'The 7, 9.5 and 12 m engineering brake-gap settings produced distinct positive source-measured minimum gaps in the 600-frame synthetic CPU probe; these are coverage points, not legal bounds.',
                    'spacing_rationale': '2.5 m yields both endpoints and a midpoint with distinct sampled follower histories at 20 Hz in the source-shaped CPU probe.',
                    'feasibility_evidence': 'traffic-effect-sweep-probe.json, sha256 '+sha(HERE/'traffic-effect-sweep-probe.json')+'; synthetic diagnostic only; Native realization pending.',
                }],
                'landmarks': [],
                'variable_assignments': assignments('reference', binding),
                'recording_description': recording,
            }
        elif slug == 'safe-operation':
            probe = read(HERE/'safe-operation-sweep-probe.json')
            settings = [row['hazard_gap_setting_m'] for row in probe['probe_rows']]
            if not probe['passed'] or settings != [6.0, 8.0, 10.0] or probe['original_native_observed']:
                raise ValueError('Safe-operation engineering probe changed')
            recording = deepcopy(old['safe_operation_stop']['recording_description'])
            recording['channels'].append({
                'name': 'hazard_center_gap_m', 'unit': 'm',
                'method': 'derive ego-to-hazard center separation from original Native actor position rows; report minimum over the stop window',
                'sampling_rate_hz': 20, 'time_window': 'all 600 frames / 30 seconds',
                'reference_frame': 'original CARLA frame joined to four video sources',
                'uncertainty': '50 ms sampling; setpoint may differ from realized minimum; original Native capture required',
            })
            spec = {
                'sweep_id': 'c179480-safe-operation-gap',
                'target_law_id': template['law_id'],
                'judgment_refs': [item],
                'rationale': 'Sample source-visible hazard placement while holding ego stop, following traffic and governing-control designation fixed; preserve original hazard and ego histories for independent safety review.',
                'status': 'complete', 'mode': 'one_dimensional',
                'axes': [{
                    'variable': 'hazard_center_gap_m', 'observable': 'hazard_center_gap_m',
                    'unit': 'm', 'min': 6.0, 'max': 10.0, 'spacing': 2.0,
                    'measurement': {
                        'method': 'derive center separation from original ego and hazard actor positions on each synchronized CARLA frame',
                        'time_window': 'all 600 frames / 30 seconds including the complete roadway stop',
                        'statistic': 'min',
                    },
                    'range_rationale': '6, 8 and 10 m source-shaped diagnostic placements retain positive, distinct lane-visible hazard gaps across the 600-frame CPU sample; these are physical coverage points only.',
                    'spacing_rationale': '2 m includes both endpoints and one midpoint and produces three distinct 20 Hz hazard histories with unchanged ego and follower sources.',
                    'feasibility_evidence': 'safe-operation-sweep-probe.json, sha256 '+sha(HERE/'safe-operation-sweep-probe.json')+'; synthetic geometry only; Native realization pending.',
                }],
                'landmarks': [],
                'variable_assignments': assignments('safe_operation_stop', binding),
                'recording_description': recording,
            }
        elif slug == 'governing-law':
            probe = read(HERE/'governing-law-sweep-probe.json')
            settings = [row['red_onset_s'] for row in probe['probe_rows']]
            if not probe['passed'] or settings != [9.0, 11.0, 13.0] or probe['original_native_observed']:
                raise ValueError('Governing-law engineering probe changed')
            recording = deepcopy(old['law_required_stop']['recording_description'])
            recording['channels'].append({
                'name': 'governing_red_onset_s', 'unit': 's',
                'method': 'derive first red-state transition from original traffic-light readback rows; retain ego association separately',
                'sampling_rate_hz': 20, 'time_window': 'all 600 frames / 30 seconds',
                'reference_frame': 'original CARLA frame joined to four video sources',
                'uncertainty': '50 ms sampling; commanded light phase may differ from observed transition; governing applicability requires independent review',
            })
            spec = {
                'sweep_id': 'c179480-governing-red-onset',
                'target_law_id': template['law_id'],
                'judgment_refs': [item],
                'rationale': 'Sample source-visible red onset around the measured stop while retaining the frozen other-vehicle cell, ego and follower trajectories, light identity and association history. Legal applicability and compliance remain unresolved.',
                'status': 'complete', 'mode': 'one_dimensional',
                'axes': [{
                    'variable': 'governing_red_onset_s', 'observable': 'governing_red_onset_s',
                    'unit': 's', 'min': 9.0, 'max': 13.0, 'spacing': 2.0,
                    'measurement': {
                        'method': 'derive first red transition from original surveyed light actor state on synchronized CARLA frames; retain ego-control association and stop history',
                        'time_window': 'all 600 frames / 30 seconds including the complete roadway stop',
                        'statistic': 'first',
                    },
                    'range_rationale': '9, 11 and 13 second synthetic phase settings yield distinct source-visible transitions before, at and after the sampled ego stop; these are engineering coverage points, not legal boundaries.',
                    'spacing_rationale': '2 seconds includes both endpoints and one midpoint with distinct 20 Hz control histories while keeping light identity and the focal other vehicle fixed.',
                    'feasibility_evidence': 'governing-law-sweep-probe.json, sha256 '+sha(HERE/'governing-law-sweep-probe.json')+'; synthetic control phase only; Native realization pending.',
                }],
                'landmarks': [],
                'variable_assignments': assignments('law_required_stop', binding),
                'recording_description': recording,
            }
        specs.append(spec)
    canonical = {'cell_id': binding['cell_id'], 'actor': binding['actor'],
                 'status': 'draft', 'cases': entries, 'sweep_specs': specs,
                 'sweeps_expanded': False}
    enriched_template = deepcopy(template)
    for judgment in enriched_template['structure']['judgment_calls_needed']:
        observable = next(read(PROPOSALS/('judgment_observables_'+slug+'.json'))
            for slug in ('traffic_movement', 'safe_operation', 'legal_compliance')
            if read(PROPOSALS/('judgment_observables_'+slug+'.json'))['phrase'] == judgment['phrase'])
        judgment['observable_requirements'] = observable['observable_requirements']
    expand_sweeps(canonical, (enriched_template,), binding)
    write(PROPOSALS/'canonical-cases.json', canonical)
    names = {'relevance_batch': 'relevance_batch.json',
             'relevance': 'relevance.json', 'template': 'template.json',
             'bindings': 'bindings.json', 'cases': 'canonical-cases.json'}
    stages = {key: {'path': 'proposals/'+filename,
                    'sha256': sha(PROPOSALS/filename)} for key, filename in names.items()}
    stages['judgment_observables'] = [
        {'path': 'proposals/judgment_observables_'+slug+'.json',
         'sha256': sha(PROPOSALS/('judgment_observables_'+slug+'.json'))}
        for slug in ('traffic_movement', 'safe_operation', 'legal_compliance')]
    index = {'format': 'worker-semantic-delivery', 'assignment_id': HERE.name,
             'stages': stages}
    write(PROPOSALS/'semantic-index.json', index)
    return {'cases': len(canonical['cases']), 'incomplete_sweeps': sum(s['status']=='incomplete' for s in specs),
            'semantic_index_sha256': sha(PROPOSALS/'semantic-index.json')}


if __name__ == '__main__':
    print(json.dumps(build(), sort_keys=True))
