"""Bind a candidate official device to original Native road and signal inventory.

A map signal and operator observation are source candidates, not a legal finding
that the exception governs either opposing left turn.
"""
from hashlib import sha256
from xml.etree import ElementTree


def verify_device_candidate(opendrive_text, approach_road_ids, survey):
    if not isinstance(opendrive_text, str) or not opendrive_text.strip():
        raise ValueError('Missing original OpenDRIVE bytes')
    digest = sha256(opendrive_text.encode('utf-8')).hexdigest()
    if survey.get('opendrive_sha256') != digest:
        raise ValueError('Operator device survey is stale for the Native map')
    if survey.get('source_kind') != 'operator_observed_native_device':
        raise ValueError('Device direction needs an original operator observation')
    if not survey.get('instruction_text') or not survey.get('observation_reference'):
        raise ValueError('Device instruction or original observation reference is missing')
    if survey.get('observed_direction') != 'directs_alternate':
        raise ValueError('Operator observation does not identify alternate crossing direction')
    road_id = survey.get('road_id')
    signal_id = survey.get('signal_id')
    if road_id not in approach_road_ids or not isinstance(signal_id, str) or not signal_id:
        raise ValueError('Survey device is outside the selected approach roads')
    root = ElementTree.fromstring(opendrive_text)
    matches = []
    for road in root.findall('road'):
        if road.get('id') != str(road_id):
            continue
        for signal in road.findall('./signals/signal'):
            if signal.get('id') == signal_id:
                matches.append(signal)
    if len(matches) != 1:
        raise ValueError('Original map does not uniquely identify the surveyed device')
    return {'governing_device':'directs_alternate',
            'candidate_road_signals':[{'road_id':road_id,'signal_id':signal_id,
                                       'opendrive_sha256':digest}],
            'candidate_instruction_text':survey['instruction_text'],
            'observation_reference':survey['observation_reference'],
            'direction_claim_source':'operator observation, pending independent review',
            'legal_device_applicability':'unreviewed'}
