"""Source-defined entry timing; no legal simultaneity or yielding verdict."""
FAMILY = 'C111294-250-2-entry-timing-v2'
PHRASE = 'at approximately the same time'
RATIONALE = 'Observe equal scheduling and signed relative entry-time offsets with all other scene/controller settings fixed. Approximate simultaneity and yielding meanings remain unresolved.'

def selection(definition, metadata):
    if definition.get('paired_probe_id') != FAMILY:
        return None
    if definition.get('target_law_id') != 'NRS-484B-250-2' or definition.get('rationale') != RATIONALE or definition.get('probe', {}).get('primary_variable') != 'commanded_entry_time_offset' or (definition.get('deliberate_differences') != ['commanded_entry_time_offset']) or (definition.get('unresolved_judgment_calls') != [PHRASE]):
        raise ValueError('Entry timing authored association differs')
    refs = metadata.get('label_record', {}).get('legal_judgment', {}).get('references', [])
    if {r.get('phrase') for r in refs if isinstance(r, dict)} != {PHRASE}:
        return {'specs': [], 'unresolved': [{'reason': 'entry_timing_source_bound_classification_reference_pending'}]}
    channels = definition.get('recording_description', {}).get('channels', [])
    paths = ['definition.rationale', 'definition.probe', 'definition.deliberate_differences']
    specs = []
    for role in ('ego', 'other'):
        for q, unit in [('kin.speed', 'm/s'), ('kin.position', 'm'), ('intersection_entry_time', 's')]:
            event = q == 'intersection_entry_time'
            specs.append({'observable': q, 'unit': unit, 'road_user': 'subject' if role == 'ego' else {'source_role': 'other', 'requires_source_binding': True}, 'phrase': PHRASE, 'source_variables': ['ego_intersection_entry_time' if role == 'ego' else 'other_vehicle_intersection_entry_time'] if event else [('ego_speed' if role == 'ego' else 'other_vehicle_speed') if q == 'kin.speed' else 'ego_trajectory' if role == 'ego' else 'other_vehicle_trajectory'], 'authored_paths': paths, 'statistic': 'instant', 'entry_timing_role': role, **({'event_source': {'method': 'original_footprint_intersection_entry', 'path': 'evidence/entry_event_evidence.jsonl'}} if event else {})})
    specs.append({'observable': 'intersection_entry_time_difference', 'unit': 's', 'road_user': 'subject', 'phrase': PHRASE, 'source_variables': ['commanded_entry_time_offset', 'intersection_entry_time_difference'], 'authored_paths': paths, 'statistic': 'instant', 'entry_timing_role': 'pair', 'event_source': {'method': 'original_footprint_intersection_entry', 'path': 'evidence/entry_event_evidence.jsonl'}})
    variables = definition.get('variable_assignments', {})
    return {'specs': specs, 'unresolved': [], 'source_channels': [{'name': c['name'], 'channel': c, 'authored_path': 'definition.recording_description.channels[' + str(i) + ']'} for i, c in enumerate(channels)], 'authored_context': [{'name': n, 'authored_value': v.get('value'), 'authored_path': 'definition.variable_assignments.' + n, 'status': 'authored_context_not_a_measurement'} for n, v in variables.items() if v.get('kind') == 'world_setup'], 'intentionally_varied': [{'name': 'commanded_entry_time_offset', 'realized_quantity': 'intersection_entry_time_difference', 'authored_value': variables.get('commanded_entry_time_offset', {}).get('value')}], 'controller_settings': [{'name': n, 'authored_value': v.get('value'), 'status': 'requested_controller_setting_not_a_measurement'} for n, v in variables.items() if v.get('kind') == 'controller']}
