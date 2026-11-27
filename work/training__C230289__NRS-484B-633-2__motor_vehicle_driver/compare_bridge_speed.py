"""Independent CPU comparison for the two source-gated speed variants."""
import json
from bridge_speed_measure import measure
from prove_bridge_speed import enc, sample


def audit(survey_below, trace_below, survey_above, trace_above):
    fixed = ('assignment_id', 'source_kind', 'fixed_cell', 'highway_source_id',
             'structure_source_id', 'structure_type', 'chapter_408_source_id',
             'administrative_declaration', 'signs')
    if any(survey_below[key] != survey_above[key] for key in fixed):
        raise ValueError('Bridge, authority, sign or cell fixed condition changed')
    for name, trace in (('below', trace_below), ('above', trace_above)):
        if trace['assignment_id'] != survey_below['assignment_id']:
            raise ValueError(name + ' assignment changed')
        if len(trace['frames']) != 600:
            raise ValueError(name + ' 600-frame duration changed')
        if [row['on_structure'] for row in trace['frames']] != [row['on_structure'] for row in trace_below['frames']]:
            raise ValueError(name + ' structure occupancy timing changed')
        if [row['vehicle_id'] for row in trace['frames']] != [row['vehicle_id'] for row in trace_below['frames']]:
            raise ValueError(name + ' participant identity changed')
    below = measure(enc(survey_below), enc(trace_below))
    above = measure(enc(survey_above), enc(trace_above))
    if below['structure_frames_above_declared_maximum'] or not above['structure_frames_above_declared_maximum']:
        raise ValueError('Measured speed comparison did not isolate below/above maximum')
    return {'comparison_id': 'bridge_declared_maximum_speed',
            'fixed_source_provenance': True,
            'below_measurement': below['max_observed_structure_speed_mph'],
            'above_measurement': above['max_observed_structure_speed_mph'],
            'physical_completion': False,
            'legal_result': None,
            'scope': 'synthetic CPU diagnostic only'}


if __name__ == '__main__':
    low_survey, low_trace = sample(35)
    high_survey, high_trace = sample(55)
    result = audit(low_survey, low_trace, high_survey, high_trace)
    high_survey['signs'][0]['source_id'] = 'different-sign'
    try:
        audit(low_survey, low_trace, high_survey, high_trace)
    except ValueError as exc:
        if str(exc) != 'Bridge, authority, sign or cell fixed condition changed':
            raise
    else:
        raise AssertionError('changed sign was accepted')
    print(json.dumps(result, sort_keys=True))
