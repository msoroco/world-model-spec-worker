"""Trace each canonical ontology atom through the existing capture and adapter.

No alias is introduced from a lexical similarity. Core accessors define field
paths; observation capability still comes from implemented, retained evidence.
"""
import hashlib
import re
from pathlib import Path


# Required on the common original-run path, independently of the selected law.
# Unsupported gestures and separately scoped observer-to-user LOS are excluded.
COMMON_CAPTURE_ATOMS = frozenset('kin.time kin.position kin.heading kin.extent kin.velocity kin.speed\nkin.accel_longitudinal kin.yaw_rate kin.path_length kin.steer_angle kin.throttle\nkin.service_brake kin.parking_brake sig.turn_indicator sig.hazard sig.brake_lamp\nsig.position_lamp sig.reverse_lamp sig.headlamp st.sight_distance'.split())
COMMON_CAPTURE_ATOMS |= frozenset('''ru.subject ru.aggregate
st.lane st.roadway st.lane_direction st.lane_adjacency st.lane_width
st.lane_marking st.lane_connectivity st.lane_enters st.curvature st.grade
st.region_geometry st.highway st.on_way st.entrance_of
dev.traffic_signal dev.stop_sign dev.yield_sign dev.speed_limit_sign
dev.regulatory_sign dev.lane_control_signal dev.position dev.governs dev.inoperative
env.darkness env.precipitation env.wet_road'''.split())


def common_profile_complete(report):
    """An old completeness boolean cannot attest unevaluated common fields."""
    profile=report.get('reconstruction',report)
    if not isinstance(profile,dict):return False
    required=profile.get('required_atoms',profile.get('required_observations',[]))
    return (report.get('required_measurements_complete')is True
        and profile.get('required_measurements_complete')is True
        and isinstance(required,list)and all(isinstance(a,str)for a in required)
        and COMMON_CAPTURE_ATOMS<=set(required))


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inventory(library, capabilities, markdown=None):
    from .adapter import full_core, atom_ids
    core = full_core(library)
    text = (core / 'Vocab/Atoms.lean').read_text()
    ids = atom_ids(library)
    docs = Path(markdown) if markdown else Path(library).parent / 'ontology/ATOMS.md'
    documented = set(re.findall(r'^\| `((?:ru|kin|st|dev|sig|env|rel)\.[a-z_]+)`', docs.read_text(), re.M))
    if set(ids)-documented:
        raise ValueError('Runtime atoms lack ontology documentation: ' + str(sorted(set(ids)-documented)))
    deferred = sorted(documented-set(ids))
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
        if atom=='st.sight_along_way':scope='observer and way'
        if atom=='st.sight_distance':scope='subject-associated region in this scene'
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
                     'limitation': ('Native light state maps to off/left/right; hazard is separate and missing state remains unknown.' if atom=='sig.turn_indicator' else 'Per-frame/entity availability must be checked; capability is not observed presence.') if available else 'No validated end-to-end source implementation; unknown, never false.',
                     'mapping_source': 'Pinned Lean accessor and implemented adapter capability, not a union of term names'})
    return {'version': 2, 'implementation_sha256': digest(__file__), 'sources': {str(p): digest(p) for p in [docs, core/'Vocab/Atoms.lean', core/'Vocab/Ontology/Ids.lean', core/'Runtime/Decode.lean']},
            'atoms': rows, 'ontology_inventory_complete': not deferred,
            'runtime_inventory_complete': True,
            'consumer_blocked_atoms': [{'atom': atom, 'reason': 'documented_without_installed_runtime_support'} for atom in deferred],
            'physical_inventory_completeness': 'requires per-recording source evidence',
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
    if name=='st_grade':return 'users[].road_grade + users[].kin.heading'
    if name=='st_curvature':return 'users[].road_curvature'
    if name=='st_sight_along_way':return 'users[].sight_along_way: [highway_region_id, metres] pairs'
    if name=='st_travel_region':return 'Core union of lane, roadway, shoulder, bicycle_lane_or_path and intersection kinds'
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
    if atom=='st.highway':return 'Measured native full-surface envelope; original public designation or explicit authored road-access convention, preserving private exclusions and verified way identity'
    if atom=='st.on_way':return 'Verified native road identity, exact native strip intervals and source-bound entrance relationships; never containment or nearest-road guessing'
    if atom=='st.bicycle_lane_or_path':return 'Complete native biking-lane inventory and verified source facility roles; an empty inventory emits no object'
    if atom=='dev.lane_control_signal':return 'Complete retained native control taxonomy and verified constructed asset roles; no overhead lane controller is instantiated by this source version'
    if atom=='ru.child':return 'Native walker age where available; the ontology excludes users observed not to be pedestrians'
    if atom=='st.lane_direction':return 'Native constant heading or measured local chord on a sampled curved-lane partition'
    if atom=='st.lane_connectivity':return 'Explicit native lane links, verified unique road continuations, and observed terminal ends in complete generated maps'
    if atom=='kin.speed':return 'Euclidean norm of original horizontal world velocity; raw vertical velocity retained separately in evidence'
    if atom=='kin.accel_longitudinal':return 'Original world ax,ay dotted with normalized measured horizontal body heading (forward XY projection); signed m/s²; normalized_horizontal_heading_dot_v1; vertical acceleration excluded'
    if atom=='kin.steer_angle':return 'Negative mean of measured FL_Wheel/FR_Wheel readbacks (front_wheel_mean_v1), or negative Front_Wheel on validated two-wheel layouts (single_front_v1); both raw pair samples required'
    if atom=='dev.inoperative':return 'Installed signal head: verified valid indication excludes inoperability; verified dark and uncovered establishes it; missing or conflicting evidence remains unresolved'
    if atom.startswith('kin.'): return 'Original live actor telemetry/applied state; finite differences where explicitly declared'
    if atom.startswith('sig.'): return 'Original actor.get_light_state; no inference from controls'
    if atom.startswith('dev.'): return 'Native recorded device/landmark state and observed controlsTrafficOf edges'
    if atom.startswith('ru.'): return 'Recorded CARLA actor identity and supported blueprint classification'
    if atom == 'st.sight_distance':
        from .visibility import METHOD_DESCRIPTION
        return METHOD_DESCRIPTION
    if atom == 'rel.visible': return 'Original subject-reference-to-actual-body collision rays; retained blockers and method'
    if atom.startswith('rel.'): return 'Recorded body/lane geometry; only contract-permitted Core computation or measured relation'
    if atom.startswith('st.'): return 'Recorded native OpenDRIVE/graph/map facts and declared spatial measurement'
    return 'Original CARLA world weather; classifications only by documented methods'


def units(atom):
    return {'kin.time':'ms', 'kin.position':'m', 'kin.heading':'finite nonzero vector; unit length recommended', 'st.lane_direction':'finite nonzero vector; unit length recommended', 'kin.velocity':'m/s',
            'kin.speed':'m/s', 'kin.accel_longitudinal':'m/s²', 'kin.yaw_rate':'deg/s',
            'kin.extent':'m (half sizes)', 'kin.steer_angle':'deg', 'kin.path_length':'m',
            'kin.throttle':'ratio', 'kin.service_brake':'ratio', 'st.grade':'ratio',
            'st.curvature':'1/m', 'st.lane_width':'m', 'st.sight_distance':'m',
            'dev.speed_limit_sign':'m/s', 'rel.centre_distance':'m', 'rel.surface_gap':'m',
            'rel.longitudinal_overlap':'m'}.get(atom, 'typed field/enum/bool; see pinned contract')


def validate_required_atoms(required, library, source):
    """Names in diagnostics must belong to the pinned runtime atom catalogue."""
    from .adapter import atom_ids
    invalid = sorted(set(required)-set(atom_ids(library)))
    if invalid:
        raise ValueError('Unknown required atom IDs at '+str(source)+': '+', '.join(invalid))


def required_coverage(required, capability, scenes, inventory_observations=None, entrance_references=None, *, structure_source_ids=None):
    """Check source scope plus per-frame values, never just a decoder receipt."""
    required=set(required)
    checks = {}; missing = []; scopes=None
    for atom in sorted(set(required)):
        inventory = None
        cap = capability['atoms'].get(atom)
        if cap is None:
            if atom != 'sig.hand_signal':raise ValueError('Unknown required atom: '+atom)
            cap='absent'
        reason = None
        if atom=='st.region_geometry'and cap!='absent'and scopes is None:
            sources=structure_source_ids if structure_source_ids is not None else [None]*len(scenes)
            if len(sources)!=len(scenes):raise ValueError('Geometry source scope does not cover every scene')
            scopes=[_observation_scope(s,ids,'st.region_geometry'in required)for s,ids in zip(scenes,sources)]
        if cap == 'absent': reason = 'unsupported_atom'
        elif not scenes: reason = 'empty_trace'
        elif atom == 'st.entrance_of':
            refs = entrance_references or []
            if not refs:
                # Common map association acquisition is independent of whether
                # the selected law names a particular stopping reference.
                if any(region.get('entrance_of')is None for scene in scenes
                       for region in scene.get('structures',[])
                       if region.get('kind')in ('stop_line','crosswalk')):
                    reason='missing_observed_entrance_association'
            else:
                for ref in refs:
                    for index in range(ref['start_frame'], ref['end_frame'] + 1):
                        if index >= len(scenes):
                            reason = 'entrance_reference_outside_trace'; break
                        region = next((r for r in scenes[index].get('structures', [])
                                       if r['id'] == ref['region_id']), None)
                        if region is None or region['kind'] not in ('stop_line', 'crosswalk'):
                            reason = 'case_entrance_reference_missing'; break
                        association = region.get('entrance_of')
                        if association is None:
                            reason = 'case_entrance_association_unknown'; break
                        if association == [] and ref.get('empty_receipts', {}).get(index) != 'observed_empty':
                            reason = 'unverified_empty_entrance_association'; break
                    if reason: break
        else:
            inventory = (inventory_observations or {}).get(atom)
            if inventory is None and atom == 'dev.inoperative':
                inventory = (inventory_observations or {}).get('dev.traffic_signal')
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
                    from .inventory_observations import STATIC_KINDS, STATIC_DEVICE_KINDS
                    family, _, kind = atom.partition('.')
                    if atom == 'dev.inoperative':kind = 'traffic_signal'
                    expected_family = 'dev' if kind in STATIC_DEVICE_KINDS else 'st'
                    domain = ('devices' if family == 'dev' else 'structures') if kind in STATIC_KINDS and family == expected_family else None
                    if domain is None or any(s.get('kind') == kind for s in scene.get(domain, [])):
                        raise ValueError('Verified absence contradicts current Core entities')
                    continue
                if not _observed(scene, atom, cap,scopes[index]if scopes is not None else None):
                    reason = 'unknown_inventory' if receipt else 'missing_observation'; break
        checks[atom] = {'passed': reason is None, 'capability': cap, 'reason': reason}
        if inventory is not None:
            from collections import Counter
            checks[atom]['observation_status_counts'] = dict(Counter(r['status'] for r in inventory))
        if reason: missing.append(atom)
    return {'passed': not missing, 'atoms': checks, 'missing': missing}


from .compatibility import LANES

WAY_CARRIER_KINDS = LANES | {'roadway','one_way_roadway','shoulder','crosswalk',
    'stop_line','median_or_divider','intersection','bicycle_lane_or_path'}



def _observation_scope(scene, source_ids=None, geometry_required=False):
    """One assessment-local context from current verified source identities.

    Explicit IDs come from existing final native/source projection. Historical
    validated traces can instead use any producer-complete occupancy marker:
    recompute emits one only after checking every final identity/shape. A Core
    decode alone does not establish this source precondition.
    """
    regions=scene.get('structures',[]);ids=[r['id']for r in regions]
    users=scene.get('users',[]);tracks=[u['track']for u in users]
    unique=len(ids)==len(set(ids));by={r['id']:r for r in regions}
    complete=set(scene.get('occupancy_observed',[]))&set(tracks)
    references=all(t in tracks and r in by for t,r in scene.get('occupies',[]))
    inferred=complete and unique and len(tracks)==len(set(tracks))and references
    sources=(set(ids)if inferred else set())if source_ids is None else set(source_ids)
    subject=scene.get('subject');occupied={r for t,r in scene.get('occupies',[])if t==subject}
    subject_known=(tracks.count(subject)==1 and subject in complete and unique
                   and occupied<=set(ids)and occupied<=sources)
    kinds={'roadway','one_way_roadway'};status='unknown'
    if subject_known:
        relevant=[by[i]for i in occupied]
        known=all(isinstance(r.get('kind'),str)and
            ('roadway'not in r.get('unobserved_kinds',[])if r['kind']in kinds else
             r['kind']not in r.get('unobserved_kinds',[])and not kinds.intersection(r.get('unobserved_kinds',[])))for r in relevant)
        if known:status='applicable'if any(r['kind']in kinds for r in relevant)else'empty'
    geometry=None
    if geometry_required or status=='empty':
        from shapely.geometry import Polygon
        geometry=bool(regions)and unique and set(ids)<=sources
        if geometry:
            for region in regions:
                try:shape=Polygon(region['boundary'])
                except (KeyError,TypeError,ValueError):geometry=False;break
                if shape.is_empty or not shape.is_valid or shape.area<=0:geometry=False;break
    if status=='empty':status='known_empty_not_applicable'if geometry else'unknown'
    return {'geometry':geometry,'roadway':status,'occupied_regions':[by[i]for i in occupied if i in by]}


def observed(scene, atom, cap, *, structure_source_ids=None):
    scope=_observation_scope(scene,structure_source_ids,atom=='st.region_geometry')if atom=='st.region_geometry'else None
    return _observed(scene,atom,cap,scope)


def _observed(scene, atom, cap, scope=None):
    family, term = atom.split('.')
    users = scene.get('users', [])
    if cap == 'subject' and family != 'rel': users = [u for u in users if u['track'] == scene.get('subject')]
    if family == 'kin':
        if term in ('throttle','service_brake','parking_brake','steer_angle','gear','engine_running'):
            users = [u for u in users if not (u.get('classes') is not None and
                     'pedestrian' in u['classes'] and 'pedestrian' not in u.get('unobserved_classes', []))]
            if not users:return True
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
    if family == 'sig':
        if term in ('turn_indicator','hazard','brake_lamp','headlamp','position_lamp','reverse_lamp'):
            users = [u for u in users if not (u.get('classes') is not None and
                     'pedestrian' in u['classes'] and 'pedestrian' not in u.get('unobserved_classes', []))]
            if not users:return True
        return bool(users) and all(u.get('sig', {}).get(term) is not None for u in users)
    if family == 'st':
        structures=scene.get('structures', [])
        if term == 'on_way':
            return all(region.get('ways') is not None for region in structures
                       if region.get('kind') in WAY_CARRIER_KINDS)
        if term=='region_geometry':return bool(scope['geometry'])
        if term in ('curvature','grade'):
            field='road_'+term
            return bool(users)and all(u.get(field)is not None and
                (term!='grade'or u.get('kin',{}).get('heading')is not None)for u in users)
        if term=='sight_distance':
            occupied={r for t,r in scene.get('occupies',[])if t==scene.get('subject')}
            relevant=[r for r in structures if r['id']in occupied and r.get('kind')in ('lane','roadway','one_way_roadway')]
            return bool(relevant)and all(r.get(term)is not None for r in relevant)
        field={'lane_direction':'direction','lane_adjacency':'count','lane_connectivity':'leads_to','lane_enters':'enters_intersection','lane_marking':'marking_left','lane_width':'width'}.get(term)
        if field:
            lanes=[s for s in structures if s['kind']=='lane']
            if term == 'lane_marking':
                return bool(lanes) and all(all(s.get('lane',{}).get(side) is not None
                    for side in ('marking_left','marking_right')) for s in lanes)
            return bool(lanes) and all(s.get('lane',{}).get(field) is not None for s in lanes)
        # Presence assertions are supported only by observed entities; empty-domain
        # absence needs a separately verified complete inventory.
        return any(s['kind']==term and term not in s.get('unobserved_kinds', []) for s in structures)
    if family == 'dev':
        devices=scene.get('devices', [])
        if term in ('position','governs'):return all(d.get(term) is not None for d in devices)
        if term=='inoperative':
            heads=[d for d in devices if d['kind']=='traffic_signal']
            return bool(heads) and all(d.get('inoperative') is not None for d in heads)
        matching=[d for d in devices if d['kind']==term]
        if term=='traffic_signal':return bool(matching) and all(d.get('indications') for d in matching)
        if term=='speed_limit_sign':return bool(matching) and all(d.get('speed_value') is not None and d.get('speed_kind') is not None for d in matching)
        if term=='regulatory_sign':return bool(matching) and all(d.get('code')is not None and isinstance(d.get('conditions'),dict)for d in matching)
        if term=='lane_control_signal':return bool(matching) and all(d.get('lane_control')is not None for d in matching)
        return bool(matching)
    if family == 'rel':
        return bool(users) and all(all(u.get('kin',{}).get(k) is not None for k in ('position','heading','extent')) for u in users)
    return False


def gaps(scene, required, *, capability=None, static_inventory=None, limitations=None, lane_entry_applicability=None, applicability=None, structure_source_ids=None):
    """Conservative field diagnostics, separate from inventory and rule support."""
    required=set(required);scope=None
    out=[]
    for atom in required:
        cap=(capability or {}).get('atoms',{}).get(atom,'exact')
        if cap=='absent' or (capability is not None and atom not in capability.get('atoms',{})):
            if limitations is not None:limitations[atom+':unsupported_by_source']+=1
            continue
        if atom=='st.region_geometry'and scope is None:
            scope=_observation_scope(scene,structure_source_ids,'st.region_geometry'in required)
        family,term=atom.split('.')
        inventory_kind='traffic_signal'if atom=='dev.inoperative'else term
        inventory=(static_inventory or {}).get('kinds',{}).get(inventory_kind)
        if family in ('st','dev') and inventory is not None and inventory['count']==0:
            entities=scene.get('devices' if family=='dev' else 'structures',[])
            if any(entity.get('kind')==inventory_kind for entity in entities):
                raise ValueError('Verified zero inventory contradicts present '+inventory_kind)
            continue
        if atom in ('dev.stop_sign','dev.yield_sign','dev.regulatory_sign','dev.speed_limit_sign','dev.lane_control_signal') and not any(
                d.get('kind')==term for d in scene.get('devices',[])):
            if limitations is not None:limitations[atom+':unknown_inventory']+=1
            continue
        if atom=='st.lane_enters' and lane_entry_applicability is not None:
            lanes=[region for region in scene.get('structures',[]) if region['kind'] in ('lane','reserved_lane','turn_lane','centre_turn_lane')]
            known=True;unknown_applicability=False
            for lane in lanes:
                applicable=lane_entry_applicability.get(lane['id'])
                if applicable is None:
                    unknown_applicability=True
                elif applicable and lane.get('lane',{}).get('enters_intersection') is None:known=False
            if unknown_applicability and limitations is not None:limitations[atom+':unknown_applicability']+=1
        elif atom=='sig.hand_signal':known=False
        elif atom=='st.entrance_of':
            marks=[r for r in scene.get('structures',[])if r['kind']in ('stop_line','crosswalk')]
            known=all(r.get('entrance_of')is not None for r in marks)
        elif atom in ('st.grade','st.curvature'):
            known=_observed(scene,atom,cap)
            if applicability is not None:applicability[atom+':'+('observed_user_profiles'if known else'unknown_user_profile')]+=1
        elif atom=='st.on_way':
            known=_observed(scene,atom,cap,scope)
        elif atom=='st.sight_along_way':
            known=all(bool(u.get('sight_along_way'))for u in scene.get('users',[]))
        elif atom=='dev.governs':
            known=all(d.get('governs')is not None for d in scene.get('devices',[]))
        elif atom in ('dev.traffic_signal','dev.inoperative'):
            heads=[d for d in scene.get('devices',[])if d['kind']=='traffic_signal']
            if not heads:
                signal_inventory=(static_inventory or {}).get('kinds',{}).get('traffic_signal')
                if signal_inventory is None or signal_inventory.get('count')!=0:
                    if limitations is not None:limitations[atom+':unknown_inventory']+=1
                continue
            known=all(bool(d.get('indications'))if atom=='dev.traffic_signal'else d.get('inoperative')is not None for d in heads)
        else:known=_observed(scene,atom,cap,scope)
        if not known:out.append(atom)
    return out
