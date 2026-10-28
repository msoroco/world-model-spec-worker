"""Trace each canonical ontology atom through the existing capture and adapter.

No alias is introduced from a lexical similarity. Core accessors define field
paths; observation capability still comes from implemented, retained evidence.
"""
import hashlib
import re
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inventory(library, capabilities, markdown=None):
    from .adapter import full_core, atom_ids
    core = full_core(library)
    text = (core / 'Vocab/Atoms.lean').read_text()
    ids = atom_ids(library)
    docs = Path(markdown) if markdown else Path(library).parent / 'ontology/ATOMS.md'
    documented = set(re.findall(r'^\| `((?:ru|kin|st|dev|sig|env|rel)\.[a-z_]+)`', docs.read_text(), re.M))
    if set(ids) != documented:
        raise ValueError('Ontology/Markdown mismatch: ' + str(sorted(set(ids) ^ documented)))
    definitions = dict(re.findall(r'^def ((?:ru|kin|st|dev|sig|env|rel)_[a-z_]+)\b(.*?)(?=^def |^--|\Z)', text, re.M | re.S))
    rows = []
    for atom in ids:
        name = atom.replace('.', '_')
        if name not in definitions:
            raise ValueError('Missing Lean atom definition: ' + atom)
        body = definitions[name]
        family, term = atom.split('.')
        scope = {'ru': 'road user', 'kin': 'road user', 'st': 'region', 'dev': 'device',
                 'sig': 'road user', 'env': 'scene', 'rel': 'relation'}[family]
        path = json_paths(name, definitions)
        attributes={key:{'lean_definition':key,'contract':value.strip(),
                         'core_json_field':json_paths(key,definitions),
                         'field_mapping_status':'resolved from pinned getter and Runtime/Decode field names'}
                    for key,value in definitions.items() if key.startswith(name+'_') and key not in {i.replace('.','_') for i in ids}}
        capability = capabilities.get(atom, 'absent')
        available = capability != 'absent'
        rows.append({'atom': atom, 'lean_accessor': name, 'core_json_field': path, 'attribute_accessors':attributes,
                     'capability': capability, 'scope': 'subject' if capability == 'subject' else scope,
                     'carla_source': source(atom) if available else None,
                     'captured_evidence': 'original same-frame capture/evidence.jsonl, native graph, road.xodr' if available else None,
                     'scene_graph_representation': 'canonical native attributes/geometry and observed_evidence packet; no duplicate alias entity' if available else None,
                     'measurement_method': source(atom) if available else None,
                     'units': units(atom), 'uncertainty': capability.split(':', 1)[1] if ':' in capability else None,
                     'limitation': ('TurnSide cannot represent an observed off/hazard indicator; raw lamp bits survive, but Core direction remains unknown.' if atom=='sig.turn_indicator' else 'Per-frame/entity availability must be checked; capability is not observed presence.') if available else 'No validated end-to-end source implementation; unknown, never false.',
                     'mapping_source': 'Pinned Lean accessor and implemented adapter capability, not a union of term names'})
    return {'version': 2, 'implementation_sha256': digest(__file__), 'sources': {str(p): digest(p) for p in [docs, core/'Vocab/Atoms.lean', core/'Vocab/Ontology/Ids.lean', core/'Runtime/Decode.lean']},
            'atoms': rows, 'complete_inventory': True,
            'complete_observation_support': all(r['capability'] != 'absent' for r in rows)}


def json_paths(name, definitions):
    """Resolve getter indirection, preserving separate fields in composite atoms.

    Never concatenate independent selectors into an invented JSON path. The
    private helper calls identify enum predicates, not additional entities.
    """
    family=name.split('_',1)[0]
    root={'ru':'users[]','kin':'users[]','st':'structures[]',
          'dev':'devices[]','sig':'users[]','env':'env','rel':'relations[]'}[family]
    body=definitions[name]
    if name=='kin_time':return 't'
    if name=='ru_subject':return 'subject + users[].track'
    if family=='ru' and ('hasClass' in body or name=='ru_aggregate'):
        return 'users[].classes + users[].unobserved_classes'
    if family=='st' and 'isKind' in body:
        return 'structures[].kind + structures[].unobserved_kinds'
    if family=='dev' and 'devKind' in body:
        return 'devices[].kind + devices[].unobserved_kinds'
    if name.startswith('rel_occupies'):
        return 'occupancy_observed + occupies'
    if family=='rel' and name!='rel_visible':
        return 'relations[] override or Core geometry from users[].kin/structures[].lane'
    aliases={'leftNeighbour':'left','rightNeighbour':'right','ordinalFromLeft':'ordinal',
             'countInDirection':'count','warningLamps':'warning_lamps','doorsOpen':'doors_open'}
    def snake(field):
        return aliases.get(field,re.sub(r'([A-Z])',lambda m:'_'+m[1].lower(),field))
    # Direct Core getter chains (e.g. users[].kin.speed or scene.env.darkness).
    selectors=re.findall(r'(?:·|s|st|l)\.([A-Za-z_]+(?:\.[A-Za-z_]+)*)',body)
    skip={'contains','map','bind','user','structure','device','relation','any','id'}
    paths=[]
    base=root
    if re.search(r'\bst_lane_adjacency\b',body):base='structures[].lane'
    if name=='st_lane_adjacency':return 'structures[].lane'
    if name=='st_lane_marking':return 'structures[].lane.marking_left + structures[].lane.marking_right'
    if name=='st_region_geometry':return 'structures[].position + structures[].boundary'
    if name=='st_region_geometry_distance':return 'Core geometry from users[].kin + structures[].position/boundary'
    if name.startswith('sig_warning_lamp_'):return 'users[].sig.warning_lamps[].colour/mode/facing'
    if name=='sig_door_open_side':return 'users[].sig.doors_open'
    for selector in selectors:
        fields=[snake(f)for f in selector.split('.')if f not in skip]
        if not fields:continue
        # s.env already includes the top-level root; other scene accessors do not.
        if fields[0]=='env':fields=fields[1:]
        path=base+('.'+'.'.join(fields)if fields else '')
        if path not in paths:paths.append(path)
    # Predicates on a named compound getter use that getter's fields.
    if not paths:
        calls=[key for key in definitions if key!=name and re.search(r'\b'+re.escape(key)+r'\b',body)]
        if calls:return ' + '.join(dict.fromkeys(json_paths(key,definitions)for key in calls))
    return ' + '.join(paths)if paths else root


def source(atom):
    if atom.startswith('kin.'): return 'Original live actor telemetry/applied state; finite differences where explicitly declared'
    if atom.startswith('sig.'): return 'Original actor.get_light_state; no inference from controls'
    if atom.startswith('dev.'): return 'Native recorded device/landmark state and observed controlsTrafficOf edges'
    if atom.startswith('ru.'): return 'Recorded CARLA actor identity and supported blueprint classification'
    if atom == 'rel.visible': return 'Original subject-reference-to-actual-body collision rays; retained blockers and method'
    if atom.startswith('rel.'): return 'Recorded body/lane geometry; only contract-permitted Core computation or measured relation'
    if atom.startswith('st.'): return 'Recorded native OpenDRIVE/graph/map facts and declared spatial measurement'
    return 'Original CARLA world weather; classifications only by documented methods'


def units(atom):
    return {'kin.time':'ms', 'kin.position':'m', 'kin.heading':'unit vector', 'kin.velocity':'m/s',
            'kin.speed':'m/s', 'kin.accel_longitudinal':'m/s²', 'kin.yaw_rate':'deg/s',
            'kin.extent':'m (half sizes)', 'kin.steer_angle':'deg', 'kin.path_length':'m',
            'kin.throttle':'ratio', 'kin.service_brake':'ratio', 'st.grade':'ratio',
            'st.curvature':'1/m', 'st.lane_width':'m', 'st.sight_distance':'m',
            'dev.speed_limit_sign':'m/s', 'rel.centre_distance':'m', 'rel.surface_gap':'m',
            'rel.longitudinal_overlap':'m'}.get(atom, 'typed field/enum/bool; see pinned contract')


def required_coverage(required, capability, scenes, inventory_observations=None):
    """Check source scope plus per-frame values, never just a decoder receipt."""
    checks = {}; missing = []
    for atom in sorted(set(required)):
        cap = capability['atoms'].get(atom)
        if cap is None: raise ValueError('Unknown required atom: ' + atom)
        reason = None
        if cap == 'absent': reason = 'unsupported_atom'
        elif not scenes: reason = 'empty_trace'
        else:
            inventory = (inventory_observations or {}).get(atom)
            if inventory is not None and len(inventory) != len(scenes):
                raise ValueError('Inventory receipt does not cover every delivered scene')
            for index, scene in enumerate(scenes):
                receipt = inventory[index] if inventory is not None else None
                if receipt and receipt.get('status') == 'observed_entry_topology':
                    if atom != 'st.lane_enters':
                        raise ValueError('Wrong atom for incoming-lane topology receipt')
                    from .native_control_observations import project as project_native
                    project_native(scene, atom, receipt)
                    continue
                if receipt and receipt.get('status') == 'verified_absent':
                    domain,kind = {'st.crosswalk':('structures','crosswalk'), 'dev.traffic_signal':('devices','traffic_signal')}.get(atom,(None,None))
                    if domain is None or any(s.get('kind') == kind for s in scene.get(domain, [])):
                        raise ValueError('Verified absence contradicts current Core entities')
                    continue
                if not observed(scene, atom, cap):
                    reason = 'unknown_inventory' if receipt else 'missing_observation'; break
        checks[atom] = {'passed': reason is None, 'capability': cap, 'reason': reason}
        if (inventory_observations or {}).get(atom) is not None:
            from collections import Counter
            checks[atom]['observation_status_counts'] = dict(Counter(r['status'] for r in inventory_observations[atom]))
        if reason: missing.append(atom)
    return {'passed': not missing, 'atoms': checks, 'missing': missing}


def observed(scene, atom, cap):
    family, term = atom.split('.')
    users = scene.get('users', [])
    if cap == 'subject' and family != 'rel': users = [u for u in users if u['track'] == scene.get('subject')]
    if family == 'kin':
        return scene.get('t') is not None if term == 'time' else bool(users) and all(u.get('kin', {}).get(term) is not None for u in users)
    if atom == 'ru.subject': return any(u['track'] == scene.get('subject') for u in users)
    if family == 'ru':
        if term == 'aggregate': return bool(users) and all(u.get('classes') is not None for u in users)
        return bool(users) and all(u.get('classes') is not None and term not in u.get('unobserved_classes', []) for u in users)
    if atom == 'rel.occupies': return all(u['track'] in scene.get('occupancy_observed', []) for u in users)
    if atom == 'rel.visible':
        targets=[u['track'] for u in users if u['track'] != scene.get('subject')]
        return all(any(r['a']==scene.get('subject') and r['b']==target and r.get('visible') is not None for r in scene.get('relations', [])) for target in targets)
    if family == 'env': return scene.get('env', {}).get(term) is not None
    if family == 'sig': return bool(users) and all(u.get('sig', {}).get(term) is not None for u in users)
    if family == 'st':
        structures=scene.get('structures', [])
        if term in ('region_geometry','curvature','grade','sight_distance'):
            relevant = [s for s in structures if s['id'] in [r for t,r in scene.get('occupies',[]) if t==scene.get('subject')] and s.get('kind') in ('lane','roadway')]
            field='boundary' if term=='region_geometry' else term
            return bool(relevant) and any(s.get(field) is not None for s in relevant)
        field={'lane_direction':'direction','lane_adjacency':'count','lane_connectivity':'leads_to','lane_enters':'enters_intersection','lane_marking':'marking_left','lane_width':'width'}.get(term)
        if field:
            lanes=[s for s in structures if s['kind']=='lane']
            return bool(lanes) and all(s.get('lane',{}).get(field) is not None for s in lanes)
        # Presence assertions are supported only by observed entities; empty-domain
        # absence needs a separately verified complete inventory.
        return any(s['kind']==term and term not in s.get('unobserved_kinds', []) for s in structures)
    if family == 'dev':
        devices=scene.get('devices', [])
        if term in ('position','governs'):return bool(devices) and all(d.get(term) for d in devices)
        matching=[d for d in devices if d['kind']==term]
        if term=='traffic_signal':return bool(matching) and all(d.get('indications') for d in matching)
        if term=='speed_limit_sign':return bool(matching) and all(d.get('speed_value') is not None for d in matching)
        return bool(matching)
    if family == 'rel':
        return bool(users) and all(all(u.get('kin',{}).get(k) is not None for k in ('position','heading','extent')) for u in users)
    return False
