"""Authored, per-frame intention declarations; Core Intentions.lean owns semantics.

No fixed intention vocabulary, observed-intent inference, or assumption fallback.
"""
import copy
import hashlib
import json
import math
import re
from pathlib import Path

LEGACY_INTENT_ASSUMPTIONS = frozenset(('asm.preparing_left_turn', 'asm.exit_intent_left',
                                      'asm.exit_intent_right', 'asm.exit_intent_u_turn'))
WIRE_KEYS = frozenset(('vehicle', 'target', 'source', 'values'))


def intention_id(value):
    # Matches the supplied IntId.wellFormed ASCII snake-case contract, not an ID registry.
    return isinstance(value, str) and re.fullmatch(r'int\.[a-z0-9_]+', value) is not None


def check_assumption_ids(pairs):
    for pair in pairs:
        if not isinstance(pair, list) or len(pair) != 2 or not isinstance(pair[0], str) or not isinstance(pair[1], bool):
            raise ValueError('Explicit Core assumptions require [name, boolean]')
        if pair[0].startswith('int.') or pair[0] in LEGACY_INTENT_ASSUMPTIONS:
            raise ValueError('Intention in assumptions: '+pair[0]+'; use scoped intent_declarations with vehicle, target, source, values and scope')


def natural(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def validate_records(records, tracks=None, regions=None):
    if not isinstance(records, list):
        raise ValueError('intents must be a list')
    seen = set()
    for entry in records:
        if not isinstance(entry, dict) or set(entry) != WIRE_KEYS:
            raise ValueError('An intent has exactly vehicle, target, source, values; target is required')
        if not natural(entry['vehicle']) or not natural(entry['target']):
            raise ValueError('Intent vehicle and target must be natural entity IDs')
        if not isinstance(entry['source'], str) or not entry['source']:
            raise ValueError('Intent source must be a non-empty string')
        pair = (entry['vehicle'], entry['target'])
        if pair in seen:
            raise ValueError('Duplicate intent vehicle/target pair')
        seen.add(pair)
        if tracks is not None and pair[0] not in tracks:
            raise ValueError('Dangling intent vehicle')
        if regions is not None and pair[1] not in regions:
            raise ValueError('Dangling intent target')
        if not isinstance(entry['values'], list):
            raise ValueError('Intent values must be a list')
        ids = set()
        for value in entry['values']:
            if not isinstance(value, list) or len(value) != 2 or not intention_id(value[0]) or not isinstance(value[1], bool):
                raise ValueError('Intent values require [well-formed int.* ID, boolean]')
            if value[0] in ids:
                raise ValueError('Duplicate intention ID for vehicle/target')
            ids.add(value[0])
    return records


def validate_scene_intents(scene):
    check_assumption_ids(scene.get('assumptions', []))
    return validate_records(scene.get('intents', []), {u['track'] for u in scene['users']},
                            {r['id'] for r in scene['structures']})


def validate_context(context, *, resolve_bindings=True):
    check_assumption_ids(context.get('core_assumptions', []))
    if 'core_intents' in context:
        raise ValueError('Use intent_declarations with an explicit scope, not core_intents')
    declarations = context.get('intent_declarations', [])
    if not isinstance(declarations, list):
        raise ValueError('intent_declarations must be a list')
    bindings = context.get('intent_bindings', {})
    if not isinstance(bindings, dict) or set(bindings) - {'vehicles', 'regions'}:
        raise ValueError('intent_bindings has vehicles and regions maps')
    for category in ('vehicles', 'regions'):
        mapping = bindings.get(category, {})
        if not isinstance(mapping, dict) or any(not isinstance(k,str) or not k or not natural(v) for k,v in mapping.items()):
            raise ValueError('Intent bindings require named roles and natural entity IDs')
    for declaration in declarations:
        if not isinstance(declaration,dict) or set(declaration) != WIRE_KEYS | {'scope'}:
            raise ValueError('Intent declaration requires vehicle, target, source, values and scope')
        resolved = {k:copy.deepcopy(declaration[k]) for k in WIRE_KEYS}
        for name, category in [('vehicle','vehicles'), ('target','regions')]:
            role = resolved[name]
            if isinstance(role, str):
                if not role:raise ValueError('Empty intent role')
                if role not in bindings.get(category, {}):
                    if resolve_bindings:raise ValueError('Missing authored intent '+name+' role binding: '+role)
                    resolved[name]=0  # syntax-only placeholder, never emitted
                else:resolved[name] = bindings[category][role]
        validate_records([resolved])
        scope = declaration['scope']
        if scope == 'whole_episode':
            continue
        if not isinstance(scope,dict) or len(scope) != 1 or next(iter(scope)) not in ('original_frames','time_s'):
            raise ValueError('Intent scope is whole_episode, original_frames:[first,last], or time_s:[first,last]')
        name, window = next(iter(scope.items()))
        if not isinstance(window,list) or len(window)!=2:
            raise ValueError('Intent scope requires two inclusive endpoints')
        if any(isinstance(v,bool) or not isinstance(v,(int,float)) or not math.isfinite(v) for v in window) or window[0]>window[1]:
            raise ValueError('Invalid intent scope interval')
        if name=='original_frames' and not all(natural(v) for v in window):
            raise ValueError('Intent frame endpoints must be natural frame IDs')
    return declarations


def project(context, scene, *, original_frame=None, time_s=None):
    records=[]
    for declaration in validate_context(context):
        scope=declaration['scope']
        if scope != 'whole_episode':
            name, window=next(iter(scope.items()))
            value=original_frame if name=='original_frames' else time_s
            if value is None:
                raise ValueError('Missing original-frame/time mapping for authored intent scope')
            if not window[0] <= value <= window[1]:
                continue
        entry={k:copy.deepcopy(declaration[k]) for k in WIRE_KEYS}
        for name,category in [('vehicle','vehicles'),('target','regions')]:
            if isinstance(entry[name],str):entry[name]=context['intent_bindings'][category][entry[name]]
        records.append(entry)
    return validate_records(records,{u['track'] for u in scene['users']},{r['id'] for r in scene['structures']})


def core_contract(library):
    from traffic_spec_adapter.adapter import full_core
    core=full_core(library)
    names=['Vocab/Intentions.lean','Vocab/World.lean','Foundations/Handles.lean',
           'Runtime/Decode.lean','Language/Formula.lean','Language/Semantics.lean']
    common=Path(library)/'TrafficSpec/Core'
    paths=[core/name if (core/name).is_file() else common/name for name in names]
    if any(not p.is_file() for p in paths):
        raise ValueError('Selected full Core does not support authored intentions; supply current Intentions.lean and matching decoder')
    world=(core/'Vocab/World.lean').read_text();decoder=(core/'Runtime/Decode.lean').read_text()
    if 'structure DeclaredIntent' not in world or 'intents : List DeclaredIntent' not in world or 'def declaredIntent' not in decoder:
        raise ValueError('Selected full Core lacks the authoritative intention wire contract')
    return {'authority':str(paths[0]),
            'sources':{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
            'scope':'Declarations current per scene and vehicle/region pair; absent is unknown; no legal evaluation'}
