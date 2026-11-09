"""Agreed plans and legal premises. No measurements or verdicts are inferred."""

INTENTIONS = {
    'int.left_turn': 'Current left-turn plan at the bound target region',
    'int.right_turn': 'Current right-turn plan at the bound target region',
    'int.u_turn': 'Current U-turn plan at the bound target region',
    'int.lane_change_left': 'Current plan to enter the bound lane to the left',
    'int.lane_change_right': 'Current plan to enter the bound lane to the right',
}
LEGAL_PREMISES = {
    'asm.public_highway': 'Declared public legal status over a homogeneous recorded scope',
    'asm.way_within_city_limits': 'Subject location within municipal limits at this timestamp',
    'asm.way_within_business_or_residential_district': 'Subject location in either agreed district category',
    'asm.way_outside_business_district': 'Subject location explicitly outside a business district',
}
PHYSICAL_SHORTCUTS = frozenset({
    'asm.appropriate_signal_fixed', 'asm.driver_ascertained_lane_change_safe',
    'asm.clearly_marked_lanes', 'asm.no_crosswalk_on_approach',
    'asm.no_hand_signal', 'asm.empty_conflicting_traffic',
    'asm.proceed_cautiously_fixed_for_halt_probe',
    'asm.no_crosswalk_in_reverse_scene', 'asm.straight_reverse_no_corner_maneuver',
    'asm.synthetic_intersection_boundary', 'asm.no_inoperative_signal_exception',
    'asm.ordinary_uncontrolled_crossing_context',
})
LEGACY_DISTRICTS = frozenset({'asm.business_district', 'asm.residential_district', 'asm.other_area'})


def declared_assumptions(context):
    """Frozen synthetic legal context is a premise, not a land-use measurement."""
    result = {}
    if combined_district(context):
        result['asm.way_within_business_or_residential_district'] = True
    seen = set()
    for key, value in context.get('core_assumptions', []):
        if key in seen:
            raise ValueError('Duplicate Core assumption identity: ' + key)
        seen.add(key)
        if key in PHYSICAL_SHORTCUTS or key in LEGACY_DISTRICTS:
            raise ValueError('Use measured fields or a defined legal premise instead of ' + key)
        if key in result and result[key] != value:
            raise ValueError('Conflicting legal premise: ' + key)
        result[key] = value
    return [[key, value] for key, value in result.items()]


def repair_assumptions(values, context=None):
    """Drop legacy shortcuts, preserving unrelated legal declarations and unknowns."""
    result = [[k, v] for k, v in values if k not in PHYSICAL_SHORTCUTS | LEGACY_DISTRICTS]
    removed = [k for k, _ in values if k in PHYSICAL_SHORTCUTS | LEGACY_DISTRICTS]
    if context and combined_district(context):
        key = 'asm.way_within_business_or_residential_district'
        old = dict(result)
        if key in old and old[key] is not True:
            raise ValueError('Existing district premise contradicts frozen context')
        if key not in old:
            result.append([key, True])
    return result, removed


def combined_district(context):
    if context.get('district') == 'business_or_residential':
        return True
    parent = context.get('scene_assumptions')
    district = parent.get('district', {}) if isinstance(parent, dict) else {}
    return (isinstance(district, dict) and district.get('external_authored_assumption') is True
            and district.get('classification') in ('business_district', 'residence_district',
                                                  'residential_district', 'business_or_residential'))


def canonical_intents(records, equivalences=None):
    """Migrate only explicitly evidenced ID equivalences; preserve binding/scope.

    A movement label or final trajectory is never sufficient. The caller must
    establish the equivalence from retained declaration semantics first.
    """
    import copy
    result = copy.deepcopy(records)
    for record in result:
        values = {}
        for key, value in record['values']:
            target = (equivalences or {}).get(key, key)
            if target in values and values[target] != value:
                raise ValueError('Conflicting intention after canonical mapping')
            values[target] = value
        record['values'] = list(map(list, values.items()))
    return result


def validate_recovery(evidence, first, receipt):
    """Validate supplementary plan bindings without executing controller code."""
    import copy
    from intentions import validate_context
    from traffic_spec_adapter.roadways import boundary_key
    if receipt.get('schema')!='retained-plan-bindings-v1':raise ValueError('Unknown plan-binding receipt schema')
    sources=receipt.get('evidence',{})
    if not sources:raise ValueError('Recovered plans require original source hashes')
    for name,digest in sources.items():
        if name.startswith('traffic_spec/') or evidence.path(name) is None or evidence.used.get(name)!=digest:
            raise ValueError('Recovered plan source is not bound to original evidence: '+name)
    regions={r['id']:r for r in first.get('structures',[])}
    signatures={r['id']:r for r in receipt.get('targets',[])}
    context={'intent_declarations':copy.deepcopy(receipt.get('declarations',[])+receipt.get('scope_limits',[]))}
    for declaration in validate_context(context):
        if any(key not in INTENTIONS for key,_ in declaration['values']):raise ValueError('Recovered plan uses an unagreed intention ID')
        ident=declaration['target'];record=signatures.get(ident);region=regions.get(ident)
        if not record or not region or record['kind']!=region['kind'] or boundary_key(record['boundary'])!=boundary_key(region.get('boundary',[])):
            raise ValueError('Recovered plan target no longer matches its verified geometry')
        if not declaration['source'].startswith(('controller:','authored:')):raise ValueError('Recovered plan must identify its declared provenance')
        if declaration['scope']=='whole_episode':raise ValueError('Recovered plans require explicit frame/time bounds')
    retired=receipt.get('retire_intention_ids',[])
    if any(not key.startswith('int.') or key in INTENTIONS for key in retired):raise ValueError('Only noncanonical legacy intention IDs may be retired')
    return copy.deepcopy(receipt.get('declarations',[]))


class RetainedContext:
    """Recover only frozen premises and explicitly scoped vehicle/target plans.

    Controller flags, blinking lamps, case names and completed motion are not
    intention declarations. Sources are read through Evidence's hash checks.
    """
    def __init__(self, evidence, first, recovery=None):
        import copy
        import json
        from traffic_spec_adapter.roadways import boundary_key
        self.issues = []
        self.sources = []
        self.context = {}
        self.declarations = []
        self.frames = {}
        self.aliases = {}
        self.stats = {}
        self.unmapped = {}
        self.recovery = copy.deepcopy(recovery)
        self.retired = set()
        self.scope_limits = []
        conflicts = set()
        contexts = []
        config = evidence.path('config.json')
        config = json.loads(config.read_text()) if config else {}
        for name in ('scene_assumptions', 'authored_test_context'):
            if isinstance(config.get(name), dict):
                contexts.append(config[name]); self.sources.append('config.json:'+name)
        frozen = evidence.path('authored_context_frozen.json')
        if frozen:
            contexts.append(json.loads(frozen.read_text())); self.sources.append(frozen.name)
        for part in contexts:
            for key, value in part.items():
                if key in conflicts:continue
                if key in self.context and self.context[key] != value:
                    self.issues.append('Conflicting frozen context '+key+'; not projected')
                    self.context.pop(key, None)
                    conflicts.add(key)
                else:
                    self.context[key] = copy.deepcopy(value)
        self.premises = {}
        for key, value in self.context.get('core_assumptions', []):
            if key in LEGAL_PREMISES and type(value) is bool:
                self.premises[key] = value
        if combined_district(self.context):
            key = 'asm.way_within_business_or_residential_district'
            if self.premises.get(key) is False:
                self.issues.append('Conflicting district classification; not projected')
                self.premises.pop(key)
            else:
                self.premises[key] = True
        binding = evidence.path('intent-role-bindings.json')
        roles = copy.deepcopy(self.context.get('intent_bindings', {}))
        roles.setdefault('vehicles', {}); roles.setdefault('regions', {})
        if binding:
            receipt = json.loads(binding.read_text())
            roles['vehicles'].update(receipt.get('vehicles', {}))
            polygon = receipt.get('target_physical_polygon_native_m')
            if polygon:
                target = boundary_key([[p[0], -p[1]] for p in polygon])
                matches = [r['id'] for r in first.get('structures', [])
                           if r.get('kind') == 'intersection' and boundary_key(r.get('boundary', [])) == target]
                if len(matches) == 1 and receipt.get('region_role'):
                    roles['regions'][receipt['region_role']] = matches[0]
                else:
                    self.issues.append('Intention target lacks a unique exact physical binding')
        plan = config.get('intention_binding_plan', {})
        if binding and 'Explicit whole-episode authored left-turn intention' in plan.get('scheduling', ''):
            self.aliases = {'int.preparing_left_turn':'int.left_turn'}
        self.context['intent_bindings'] = roles
        from intentions import validate_context
        for item in canonical_intents(self.context.get('intent_declarations', []), self.aliases):
            if not item.get('values') or any(k not in INTENTIONS for k, _ in item['values']):
                self.issues.append('Legacy intention has no verified catalogue equivalence')
                continue
            candidate = dict(self.context, core_assumptions=[], intent_declarations=[item])
            try:
                validate_context(candidate)
            except ValueError as exc:
                self.issues.append('Unresolved intention declaration: '+str(exc))
                continue
            self.declarations.append(item)
        if recovery:
            self.declarations.extend(validate_recovery(evidence,first,recovery))
            self.retired=set(recovery.get('retire_intention_ids',[]))
            self.scope_limits=copy.deepcopy(recovery.get('scope_limits',[]))
            self.sources.append('Evidence-bound supplementary controller-plan receipt')
        self.context['intent_declarations'] = self.declarations
        if any(isinstance(d['scope'], dict) and 'original_frames' in d['scope'] for d in self.declarations+self.scope_limits):
            for row in evidence.rows('video_frames.jsonl'):
                if isinstance(row.get('time_s'), (int, float)):
                    self.frames[round(row['time_s']*1000)] = row.get('original_frame', row.get('carla_frame', row.get('frame')))

    def project(self, scene):
        from collections import Counter
        from intentions import project, validate_scene_intents
        changes = Counter()
        before = scene.get('assumptions', [])
        after = [[k,v] for k,v in before if k not in PHYSICAL_SHORTCUTS]
        if len(after)!=len(before):changes['removed_physical_assumptions']+=len(before)-len(after)
        old = dict(after)
        for key, value in self.premises.items():
            if key in old and old[key] != value:
                self.issues.append('Existing premise contradicts retained declaration: '+key)
            elif key not in old:
                after.append([key,value]); old[key] = value
                changes['declared_legal_premise'] += 1
        if before != after:
            scene['assumptions'] = after
            changes['context_assumption_frames'] += 1
        source = dict(self.context)
        # Assumptions are projected through their own channel above. Historical
        # planning aliases in a raw config must not disable valid declarations.
        source['core_assumptions']=[]
        source['intent_bindings'] = {k:dict(v) for k,v in self.context['intent_bindings'].items()}
        canonical = []
        try:
            canonical = project(source, scene, original_frame=self.frames.get(scene['t']), time_s=scene['t']/1000)
        except ValueError as exc:
            self.issues.append('Intention cannot be projected at this observation: '+str(exc))
        if self.retired:
            retained=[]
            for record in scene.get('intents',[]):
                values=[v for v in record['values'] if v[0] not in self.retired]
                changes['retired_noncanonical_intention_values']+=len(record['values'])-len(values)
                if values:retained.append(dict(record,values=values))
            if retained!=scene.get('intents',[]):scene['intents']=retained
        existing = {(r['vehicle'],r['target']):r for r in scene.get('intents', [])}
        for r in scene.get('intents',[]):
            for key,_ in r['values']:
                if key not in INTENTIONS:self.unmapped[key]=self.unmapped.get(key,0)+1
        for record in canonical:
            pair = record['vehicle'],record['target']
            if pair not in existing:
                scene.setdefault('intents', []).append(record);existing[pair] = record
                changes['declared_intention_records'] += 1
            else:
                item = existing[pair]
                # The current declaration proves the alias only for this exact
                # vehicle/target/source and current scope, never other actors.
                values = canonical_intents([item], self.aliases if item['source']==record['source'] else {})[0]['values']
                if values != item['values']:
                    item['values'] = values; changes['canonical_intention_values'] += 1
                old = dict(item['values'])
                for key,value in record['values']:
                    if key in old and old[key] != value:
                        self.issues.append('Conflicting current intention: '+key)
                    elif key not in old:
                        item['values'].append([key,value]);changes['declared_intention_values'] += 1
        if self.scope_limits:
            # Supplementary source evidence may narrow an old whole-episode
            # declaration. It cannot replace its truth value or its target.
            limited={(d['vehicle'],d['target'],key) for d in self.scope_limits for key,_ in d['values']}
            active=project({'intent_declarations':self.scope_limits},scene,
                original_frame=self.frames.get(scene['t']),time_s=scene['t']/1000)
            allowed={(d['vehicle'],d['target'],key):value for d in active for key,value in d['values']}
            records=[]
            for record in scene.get('intents',[]):
                values=[]
                for key,value in record['values']:
                    binding=(record['vehicle'],record['target'],key)
                    if binding in limited:
                        if binding not in allowed:
                            changes['expired_intention_values']+=1
                            continue
                        if allowed[binding]!=value:raise ValueError('Scoped plan limit contradicts the retained plan')
                    values.append([key,value])
                if values:records.append(dict(record,values=values))
            if records!=scene.get('intents',[]):scene['intents']=records
        validate_scene_intents(scene)
        self.stats['frames']=self.stats.get('frames',0)+1
        for record in scene.get('intents',[]):
            for key,value in record['values']:
                self.stats[key]=self.stats.get(key,0)+1
                if key in INTENTIONS and value is True:
                    self.stats['true_canonical_vehicle_target_values']=self.stats.get('true_canonical_vehicle_target_values',0)+1
        return changes

    def report(self):
        return {'premises':self.premises,'scoped_plan_declarations':len(self.declarations),
                'sources':self.sources,'issues':list(dict.fromkeys(self.issues)),
                'unmapped_intent_values':self.unmapped,'projected_values':self.stats,
                'unsupported_plan_policy':'No plan inferred from lamps, controller booleans, case names or motion'}


def public_road_ids(path, config, declaration=None, map_sha256=None):
    """Resolve authored road access separately from measured road geometry."""
    import xml.etree.ElementTree as ET
    roads={int(r.attrib['id']):r for r in ET.parse(path).getroot().findall('road')}
    if declaration is None:return config.get('public_way_road_ids',[])
    if (declaration.get('schema')!='authored-road-access-v1'
            or declaration.get('scope')!='entire_recorded_native_map'
            or declaration.get('default_access')!='public'
            or declaration.get('map_sha256')!=map_sha256
            or declaration.get('provenance',{}).get('kind')!='operator_approved_synthetic_convention'
            or not declaration.get('provenance',{}).get('statement')):
        raise ValueError('Public-road convention requires explicit authored scope, provenance and the original map hash')
    private=set()
    for key in ('private_road_ids','private_way_road_ids'):
        values=config.get(key,[])
        if not isinstance(values,list)or any(type(i)is not int for i in values):raise ValueError('Private-road IDs must be native integer IDs')
        private.update(values)
    if config.get('construction',{}).get('public_designation')=='private':private.update(roads)
    for ident,road in roads.items():
        if road.get('access')=='private' or any(t.get('type')=='private' for t in road.findall('type')):private.add(ident)
    authored_private=declaration.get('private_road_ids',[])
    if not isinstance(authored_private,list)or any(type(i)is not int for i in authored_private):raise ValueError('Authored private-road IDs must be native integer IDs')
    private.update(authored_private)
    if private-set(roads):raise ValueError('Private-road declaration names an unknown native road')
    return sorted(set(roads)-private)
