import re
"""Authored opposing-stream phase observables; no hazard or yielding verdict."""
FAMILY = 'C329654-253-initial-opposing-position-v1'
RATIONALE = 'Initial opposing-position and complete-stream-phase comparison; full opposing stream translation is explicitly declared, not an isolated initial-vehicle-only pose intervention; all legal judgment phrases remain unresolved'
PHRASES = {'having so yielded', 'immediate hazard'}
ROLES = ('ego', 'initial_opposing', 'further_opposing_1')
YIELD_FAMILY = 'C329654-review-yield-v3'
YIELD_RATIONALE = 'Compare ego yielding to none, initially approaching vehicle only with a farther subsequent stream, and all vehicles. Retain distance/speed at actual commitment; counterpart accommodation alone does not establish entitlement.'
SPEED_FAMILY = 'C329654-253-opposing_approach_speed-v1'
SPEED_RATIONALE = 'Fixed middle starting geometry and all held facts; vary only opposing_speed_request; all legal judgment phrases remain unresolved'
STREAM_FAMILY = 'C329654-253-subsequent_opposing_stream-v1'
STREAM_RATIONALE = 'Fixed middle starting geometry and all held facts; vary only opposing_stream_request; all legal judgment phrases remain unresolved'

def _family(definition):
    family = definition.get('paired_probe_id')
    if family == SPEED_FAMILY:
        variable, rationale = ('opposing_speed_request', SPEED_RATIONALE)
    elif family == STREAM_FAMILY:
        variable, rationale = ('opposing_stream_request', STREAM_RATIONALE)
    elif family in (FAMILY, YIELD_FAMILY, 'C329654-review-yield-v4'):
        variable = 'opposing_position_request' if family == FAMILY else 'yield_policy_request'
        rationale = RATIONALE if family == FAMILY else YIELD_RATIONALE
    else:
        return None
    if definition.get('target_law_id') != 'NRS-484B-253' or definition.get('rationale') != rationale or definition.get('probe', {}).get('primary_variable') != variable or (definition.get('deliberate_differences') != [variable]) or (set(definition.get('unresolved_judgment_calls', [])) != PHRASES):
        raise ValueError('Opposing stream authored association differs')
    roles = ROLES
    if variable in ('opposing_stream_request', 'yield_policy_request'):
        participants = definition.get('variable_assignments', {}).get('participant_configuration', {}).get('value', {})
        further = sorted((r for r in participants if re.fullmatch('further_opposing_[1-9][0-9]*', r)))
        roles = ('ego', 'initial_opposing') + tuple(further)
        if not further or set(participants) != set(roles) or further != ['further_opposing_' + str(i + 1) for i in range(len(further))]:
            raise ValueError('Authored opposing participant roles differ')
    return (variable, roles)

def selection(definition, metadata):
    family = _family(definition)
    if family is None:
        return None
    variable, roles = family
    refs = metadata.get('label_record', {}).get('legal_judgment', {}).get('references', [])
    if {r.get('phrase') for r in refs if isinstance(r, dict)} != PHRASES:
        return {'specs': [], 'unresolved': [{'reason': 'opposing_turn_source_bound_classification_reference_pending'}]}
    channels = definition.get('recording_description', {}).get('channels', [])
    by_name = {c['name']: (i, c) for i, c in enumerate(channels)}
    required = {'participant_native_state', 'participant_interaction_history', 'intersection_occupancy', 'opposing_boundary_relative_position', 'opposing_approach_speed', 'opposing_stream_count'}
    if not required <= set(by_name):
        raise ValueError('Opposing stream source channels differ')
    if not by_name['opposing_boundary_relative_position'][1]['method'].startswith('Initial opposing front minus native x=7m roadway entry boundary; raw all-frame measurements'):
        raise ValueError('Opposing boundary coordinate definition differs')
    if by_name['opposing_stream_count'][1]['method'] != 'Distinct further opposing vehicle count, excluding ego and initial opponent; all counterpart identities retained':
        raise ValueError('Opposing counted population differs')
    specs = []
    for phrase in sorted(PHRASES):
        quantities = [(q, u, r, 'participant_interaction_history') for r in roles for q, u in [('kin.position', 'm'), ('kin.speed', 'm/s')]]
        if phrase == 'having so yielded':
            quantities += [('intersection_footprint_overlap_area', 'm^2', r, 'intersection_occupancy') for r in roles]
        if phrase == 'immediate hazard':
            quantities += [('opposing_boundary_relative_position', 'm', 'initial_opposing', 'opposing_boundary_relative_position'), ('opposing_stream_count', 'count', 'ego', 'opposing_stream_count')]
        if variable == 'yield_policy_request' and phrase == 'having so yielded':
            channel = 'opposing_vehicles_cleared_before_commit'
            if channel not in by_name or by_name[channel][1]['method'] != 'Distinct opposite-direction vehicle bodies fully beyond the far intersection boundary, frozen at first actual ego turn motion; retain original body/control histories and commitment bracket':
                raise ValueError('Authored cleared-before-commit event differs')
            quantities.append((channel, 'count', 'ego', channel))
        for q, unit, role, channel in quantities:
            specs.append({'observable': q, 'unit': unit, 'road_user': 'subject' if role == 'ego' else {'source_role': role, 'requires_source_binding': True}, 'opposing_turn_role': role, 'phrase': phrase, 'statistic': 'instant', 'source_variables': [channel] + ([variable] if variable == 'yield_policy_request' or (variable == 'opposing_position_request' and q == 'opposing_boundary_relative_position') or (variable == 'opposing_stream_request' and q == 'opposing_stream_count') or (variable == 'opposing_speed_request' and q == 'kin.speed' and (role != 'ego')) else []), 'authored_paths': ['definition.rationale', 'definition.recording_description.channels[' + str(by_name[channel][0]) + ']'], 'source_uncertainty': [by_name[channel][1].get('uncertainty', 'Unknown total error; finite original scene samples')], 'association_basis': 'Authored complete-stream-phase comparison and full preceding/turn/counterpart-response history; observed motion describes each exact unresolved phrase without deciding it. Boundary-relative approach position and stream count describe immediate-hazard context; overlap history describes having-so-yielded context. Signal/weather channels remain supporting evidence, not automatically requested measurements.'})
    variables = definition.get('variable_assignments', {})
    return {'specs': specs, 'unresolved': [], 'source_channels': [{'name': c['name'], 'channel': c, 'authored_path': 'definition.recording_description.channels[' + str(i) + ']', 'status': 'source_channel_not_an_independent_measurement_requirement'} for i, c in enumerate(channels)], 'authored_context': [{'name': n, 'authored_value': v.get('value'), 'authored_path': 'definition.variable_assignments.' + n, 'status': 'authored_context_not_a_measurement'} for n, v in variables.items() if v.get('kind') == 'world_setup'], 'intentionally_varied': [{'name': variable, 'realized_quantity': 'kin.speed for every original opposing participant' if variable == 'opposing_speed_request' else 'opposing_boundary_relative_position' if variable == 'opposing_position_request' else 'opposing_stream_count' if variable == 'opposing_stream_request' else 'recorded participant motion, overlap and source cleared-before-commit count', 'authored_value': variables.get(variable, {}).get('value'), 'scope': 'Actual original opposing participant speed histories at synchronized scenes; commanded speed is not copied into readings' if variable == 'opposing_speed_request' else 'Whole opposing stream translated at fixed initial-to-further offset, not initial actor alone' if variable == 'opposing_position_request' else 'Distinct further opposing vehicles, excluding subject and initial opponent; actual complete participant inventory' if variable == 'opposing_stream_request' else 'Actual complete interaction of every authored participant; requested policy is not an atom or verdict'}], 'controller_settings': [{'name': n, 'authored_value': v.get('value'), 'status': 'requested_controller_setting_not_a_measurement'} for n, v in variables.items() if v.get('kind') == 'controller']}
