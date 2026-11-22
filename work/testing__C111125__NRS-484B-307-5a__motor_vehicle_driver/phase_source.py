"""Reviewed governing-phase source and original entry-transition observations.

This module supplies a source-bound observation, never a legal right-of-way
verdict. An actor already inside at the first sample has no observed entry.
"""
import hashlib
import json
from pathlib import Path


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load(packet_path, source_path):
    packet_path=Path(packet_path);source_path=Path(source_path)
    packet=json.loads(packet_path.read_text(encoding='utf-8'))
    source=source_path.read_bytes()
    if packet.get('format')!='c111125-reviewed-participant-phase-v1':
        raise ValueError('unknown participant phase review format')
    if packet.get('review_method')!='original-governing-signal-and-entry-rule' or not packet.get('reviewer'):
        raise ValueError('participant governing phase review missing')
    if not packet.get('source_ref') or not source or packet.get('source_sha256')!=digest(source):
        raise ValueError('participant phase source absent or hash mismatch')
    if packet.get('source_file')!=source_path.name:
        raise ValueError('participant phase source filename mismatch')
    actor_id=packet.get('participant_actor_id')
    slot=packet.get('participant_slot')
    if actor_id is None and slot not in ('vehicle','pedestrian'):
        raise ValueError('participant phase slot or actor ID missing')
    if actor_id is not None and (type(actor_id) is not int or actor_id<0):
        raise ValueError('participant phase actor ID invalid')
    if slot is not None and slot not in ('vehicle','pedestrian'):
        raise ValueError('participant phase slot invalid')
    if packet.get('participant_role') not in ('vehicle','pedestrian'):
        raise ValueError('participant phase role invalid')
    if slot is not None and packet['participant_role']!=slot:
        raise ValueError('participant phase slot and role differ')
    if slot is not None and not isinstance(packet.get('participant_blueprint_id'),str):
        raise ValueError('participant phase blueprint identity missing')
    if type(packet.get('governing_signal_actor_id')) is not int or packet['governing_signal_actor_id']<0:
        raise ValueError('governing phase actor ID invalid')
    if packet.get('permitted_entry_states')!=['Green']:
        raise ValueError('reviewed permitted-entry state inventory missing')
    if not packet.get('entry_rule_source_ref'):
        raise ValueError('entry rule source citation missing')
    return {'packet':packet,'packet_sha256':digest(packet_path.read_bytes()),
            'source_sha256':digest(source)}


def entry_observation(binding, participant, lights, *, frame, previous_inside, inside):
    """Classify an observed outside-to-inside transition from its raw phase."""
    packet=binding['packet']
    expected_id=binding.get('bound_actor_id',packet.get('participant_actor_id'))
    if participant.get('id')!=expected_id or participant.get('role')!=packet['participant_role']:
        raise ValueError('participant phase actor identity mismatch')
    if type(frame) is not int or frame<0:
        raise ValueError('participant entry frame invalid')
    if previous_inside is None or not isinstance(previous_inside,bool) or not isinstance(inside,bool):
        return {'frame':frame,'status':None,'reason':'entry_not_observed'}
    if previous_inside or not inside:
        return {'frame':frame,'status':None,'reason':'no_entry_transition'}
    matches=[item for item in lights if item.get('actor_id')==packet['governing_signal_actor_id']]
    if len(matches)!=1:
        raise ValueError('original governing phase actor absent or ambiguous')
    raw=str(matches[0].get('state','')).split('.')[-1]
    if raw not in ('Green','Yellow','Red'):
        raise ValueError('original governing phase state unknown')
    status=True if raw in packet['permitted_entry_states'] else (False if raw=='Red' else None)
    return {'frame':frame,'status':status,'reason':'reviewed_entry_phase',
            'raw_state':raw,'governing_signal_actor_id':packet['governing_signal_actor_id'],
            'packet_sha256':binding['packet_sha256'],'source_sha256':binding['source_sha256']}
