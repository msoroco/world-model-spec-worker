"""Pure authored quantity selection; never evaluates a legal standard or a trace."""
from judgment_entry_timing import selection as entry_timing_selection
from judgment_opposing_turn import selection as opposing_turn_selection

# Names describe recorded quantities, not the values of controller requests.
_OBSERVABLES = {
    'native_fog_density': ('native_fog_density', 'CARLA percent', 'subject'),
    'native_precipitation_strength': ('native_precipitation_strength', 'CARLA percent', 'subject'),
    'observed_tire_friction': ('observed_tire_friction', 'native wheel tire_friction', 'subject'),
    'ego_stopping_distance': ('observed_stopping_displacement', 'm', 'subject'),
    'observed_stopping_event': ('observed_stopping_displacement', 'm', 'subject'),
    'visibility': ('env.visibility', 'm', 'subject'),
    'nearby_vehicle_speeds': ('kin.speed', 'm/s', 'other'),
    'nearby_vehicle_trajectories': ('kin.position', 'm', 'other'),
    'traffic_queue_behind': ('kin.position', 'm', 'subject'),
    'highway_width': ('highway_width', 'm', 'subject'),
    'roadway_width': ('roadway_width', 'm', 'subject'),
    'driving_lane_width': ('st.lane_width', 'm', 'subject'),
    'left_shoulder_width': ('left_shoulder_width', 'm', 'subject'),
    'right_shoulder_width': ('right_shoulder_width', 'm', 'subject'),
    'ego_speed': ('kin.speed', 'm/s', 'subject'),
    'commanded_speed': ('kin.speed', 'm/s', 'subject'),
    'commanded_approach_speed': ('kin.speed', 'm/s', 'subject'),
    'stop_action_speed_request': ('kin.speed', 'm/s', 'subject'),
    'post_stop_speed_request': ('kin.speed', 'm/s', 'subject'),
    'leader_speed': ('kin.speed', 'm/s', 'leader'),
    'road_grade': ('st.grade', '1', 'subject'),
    'road_curvature': ('st.curvature', '1/m', 'subject'),
    'wet_road': ('env.wet_road', 'Boolean', 'subject'),
    'ice_or_snow': ('env.ice_or_snow', 'Boolean', 'subject'),
    'precipitation': ('env.precipitation', 'Boolean', 'subject'),
    'visibility_distance': ('env.visibility', 'm', 'subject'),
    'relative_speed': ('relative_speed', 'm/s', 'subject'),
    'euclidean_body_separation': ('rel.surface_gap', 'm', 'subject'),
    'target_lane_surface_gap': ('target_lane_surface_gap', 'm', 'subject'),
    'along_route_body_gap': ('along_route_body_gap', 'm', 'subject'),
    'commanded_following_gap': ('along_route_body_gap', 'm', 'subject'),
    'front_group_clear_gap_m': ('front_group_clear_gap_m', 'm', 'subject'),
    'rear_group_clear_gap_m': ('rear_group_clear_gap_m', 'm', 'subject'),
    'subject_overall_width': ('kin.extent', 'm', 'subject'),
    'lead_overall_width': ('kin.extent', 'm', 'leader'),
    'ego_trajectory': ('kin.position', 'm', 'subject'),
    'ego_turn_indicator': ('sig.turn_indicator', 'categorical', 'subject'),
    'ego_lane': ('rel.occupies', None, 'subject'),
    'ego_signal_lead_distance': ('signal_lead_distance', 'm', 'subject'),
    'ego_continuous_signal_distance_before_course_change': ('continuous_signal_distance_before_course_change', 'feet', 'subject'),
    'surrounding_vehicle_count': ('surrounding_vehicle_count', 'count', 'subject'),
    'st.sight_distance': ('st.sight_distance', 'm', 'subject'),
}


def _phrases(definition, metadata):
    refs = metadata.get('label_record', {}).get('legal_judgment', {}).get('references', [])
    phrases = [r.get('phrase') for r in refs if isinstance(r, dict) and r.get('phrase')]
    return list(dict.fromkeys(phrases))


def _associations(node, path, phrases, out):
    """Only explicit phrase-scoped observable requirement records earn links."""
    if isinstance(node, dict):
        phrase = node.get('phrase')
        requirements = node.get('observable_requirements')
        if phrase in phrases and isinstance(requirements, dict):
            for group, records in requirements.items():
                if isinstance(records, list):
                    for i, record in enumerate(records):
                        if isinstance(record, dict) and isinstance(record.get('name'), str):
                            out.setdefault(record['name'], []).append((phrase, path + '.observable_requirements.' + group + '[' + str(i) + ']'))
        for key, value in node.items():
            _associations(value, path + '.' + key, phrases, out)
    elif isinstance(node, list):
        for i, value in enumerate(node):
            _associations(value, path + '[' + str(i) + ']', phrases, out)


_SPACING_RATIONALE = ('Fixedphysicalspacingreferences; bothjudgmentsunresolved. '
    'Linkednumericboundarydefinitionsretainbelow/at/abovereferences; selectedphysicalcasesremainunlabeled. '
    'Newv6native meshcapture and closeroverview address realcapturegaps beforecomparison.')
_SPACING_PHRASES = ('whenever conditions permit', 'without danger')


def _shared_spacing_links(definition, phrases):
    """Reviewed source-authored joint association, never a law-wide fallback."""
    authored = definition.get('unresolved_judgment_calls')
    if (definition.get('paired_probe_id') != 'C102372-127-2-gap-v4'
            or definition.get('rationale') != _SPACING_RATIONALE
            or definition.get('probe', {}).get('primary_variable') != 'commanded_following_gap'
            or not isinstance(authored, list) or len(authored) != 2
            or any(not isinstance(value, str) for value in authored)
            or set(authored) != set(_SPACING_PHRASES)):
        return {}
    links = {name:[(phrase, 'definition.rationale') for phrase in phrases if phrase in authored]
             for name in ('commanded_following_gap', 'along_route_body_gap', 'euclidean_body_separation')}
    # Completed representative supplies the same authored fixed physical context.
    if 'without danger' in phrases:
        for name in ('ego_speed', 'leader_speed', 'subject_overall_width',
                     'lead_overall_width', 'road_grade', 'road_curvature'):
            links[name] = [('without danger', 'definition.rationale')]
    return links


def _reviewed_width_1272_links(definition, phrases):
    """Physical observables linked to the existing source-reviewed duty questions."""
    review=definition.get('current_legal_review_definition',{})
    questions=review.get('fact_backed_legal_questions',[])
    if (definition.get('paired_probe_id')=='C102372-127-2-lead-width-v4'
            and definition.get('probe',{}).get('primary_variable')=='lead_body_asset_width_reference_m'
            and review.get('schema')=='source-bound-legal-review-case-envelope-v1'
            and review.get('physical_case_config_and_observations_unchanged')is True
            and isinstance(review.get('root_outcome_review'),dict) and len(questions)==2
            and questions[0].get('phrase')=='which is following a truck, or combination of vehicles 80 inches or more in overall width'
            and questions[1].get('phrase')=='whenever conditions permit; without danger'):
        links={}
        for phrase in phrases:
            if phrase==questions[0]['phrase']:
                for name in ('subject_overall_width','lead_overall_width','lead_body_asset_width_reference_m'):
                    links[name]=[(phrase,'definition.current_legal_review_definition.fact_backed_legal_questions[0]')]
            elif phrase in ('whenever conditions permit','without danger'):
                for name in ('ego_speed','leader_speed','along_route_body_gap','euclidean_body_separation','road_grade','road_curvature'):
                    links.setdefault(name,[]).append((phrase,'definition.current_legal_review_definition.fact_backed_legal_questions[1]'))
        return links
    if (definition.get('paired_probe_id')!='C102372-127-2-lead-width-v4'
            or definition.get('probe',{}).get('primary_variable')!='lead_body_asset_width_reference_m'
            or review.get('schema')!='source-bound-legal-review-case-envelope-v1'
            or review.get('physical_case_config_and_observations_unchanged')is not True
            or len(questions)!=3 or not isinstance(review.get('root_outcome_review'),dict)
            or questions[0].get('phrase')!='which is following; whenever conditions permit'
            or ''.join(questions[1].get('phrase','').split())!='leaveaspaceof500feet'
            or not questions[2].get('phrase','').endswith('without danger')):
        return {}
    links={}
    for index,question in enumerate(questions):
        text=question.get('phrase','')
        names = (('ego_speed','leader_speed','subject_overall_width','lead_overall_width','lead_body_asset_width_reference_m','road_grade','road_curvature') if index==0
                 else ('along_route_body_gap','euclidean_body_separation'))
        for phrase in phrases:
            if ''.join(phrase.split()) not in ''.join(text.split()):continue
            for name in names:
                # Width qualifies the following-duty participants; road conditions
                # and actual motion address its explicitly reviewed phase/context.
                if index==0 and name in ('road_grade','road_curvature') and phrase!='whenever conditions permit':continue
                if index==0 and name in ('subject_overall_width','lead_overall_width','lead_body_asset_width_reference_m') and phrase!='which is following':continue
                links.setdefault(name,[]).append((phrase,'definition.current_legal_review_definition.fact_backed_legal_questions['+str(index)+']'))
    return links


def _reviewed_1272_branch_links(definition, phrases):
    """Named source-review physical questions, not a law-wide association."""
    family=definition.get('paired_probe_id');review=definition.get('current_legal_review_definition',{})
    if (family not in ('C102372-127-2-same-direction-lanes-v1','C102372-127-2-subject-passing-v2','C102372-review-interaction-v1')
            or review.get('schema')!='source-bound-legal-review-case-envelope-v1'
            or review.get('physical_case_config_and_observations_unchanged')is not True
            or not isinstance(review.get('root_outcome_review'),dict)):
        return {}
    questions=review.get('fact_backed_legal_questions',[]);links={}
    for index,question in enumerate(questions):
        text=''.join(question.get('phrase','').split())
        for phrase in phrases:
            if ''.join(phrase.split())not in text:continue
            if phrase=='leave a space of 500 feet':names=('along_route_body_gap','euclidean_body_separation')
            elif phrase=='whenever conditions permit':names=('ego_speed','leader_speed','along_route_body_gap','euclidean_body_separation','road_grade','road_curvature')
            elif phrase=='without danger':names=('ego_speed','leader_speed','along_route_body_gap','euclidean_body_separation','subject_overall_width','lead_overall_width','road_grade','road_curvature')
            elif phrase.startswith('while moving on a highway'):names=('same_direction_lane_count','same_direction_available_lane_count','ego_speed')
            elif phrase.startswith('which is following'):names=('subject_overall_width','lead_overall_width')
            else:continue
            for name in names:links.setdefault(name,[]).append((phrase,'definition.current_legal_review_definition.fact_backed_legal_questions['+str(index)+']'))
    # Original paired references explicitly retain the joint physical conditions/
    # accommodation questions, including when one current review isolates a proviso.
    if set(review.get('original_authored_unresolved_judgment_calls',[]))=={'whenever conditions permit','without danger'}:
        for phrase in ('whenever conditions permit','without danger'):
            if phrase not in phrases:continue
            for name in ('ego_speed','leader_speed','along_route_body_gap','euclidean_body_separation','subject_overall_width','lead_overall_width','road_grade','road_curvature','subject_passing_completion_count','surrounding_vehicle_count','same_direction_available_lane_count'):
                if not any(p==phrase for p,_ in links.get(name,[])):
                    links.setdefault(name,[]).append((phrase,'definition.rationale'))
    if family=='C102372-127-2-subject-passing-v2':
        for name in ('subject_passing_profile_enabled','leader_reference_trajectory'):
            links[name]=[(p,'definition.current_legal_review_definition.fact_backed_legal_questions')for p in phrases if p=='whenever conditions permit']
    if family=='C102372-review-interaction-v1':
        for name in ('commanded_outsider_entry','recorded_outsider_velocity','recorded_outsider_half_extents','entered_gap_vehicle_count'):
            links[name]=[(p,'definition.current_legal_review_definition.fact_backed_legal_questions')for p in phrases if p=='without danger'or p.startswith('which is following')]
    return links


def _following_1271_links(definition, phrases):
    # Reviewed authored family and the source law's explicit clause association.
    prefix = 'C102304-127-1-'
    allowed = {'separation': 'commanded_following_gap', 'cruise-speed': 'commanded_speed',
               'relative-speed': 'commanded_leader_speed_drop', 'fog': 'fog_setting',
               'precipitation': 'precipitation_setting',
               'traffic': 'additional_vehicle_count', 'friction': 'road_friction_setting'}
    family = definition.get('paired_probe_id', '')
    branch = next((key for key in allowed if family == prefix + key + '-v2'), None)
    primary = definition.get('probe', {}).get('primary_variable')
    authored = definition.get('unresolved_judgment_calls', [])
    if (not isinstance(authored,list) or any(not isinstance(p,str) for p in authored)
            or set(authored) != {'reasonable and prudent', 'having due regard'}):
        return {}
    rationale = definition.get('rationale', '')
    reviewed = {'C102304-review-cruise_speed-v1':'commanded_speed',
        'C102304-review-cruise_speed-v2':'commanded_speed',
        'C102304-review-cruise_speed-v3':'commanded_speed',
        'C102304-review-leader_slowdown-v3':'commanded_leader_speed_drop',
        'C102304-review-early_traffic-v3':'additional_vehicle_count'}
    if family in reviewed:
        if (primary != reviewed[family]
                or rationale != 'User-authorized stronger physical contrast; legal following judgments unresolved'):
            return {}
    else:
        if branch is None or primary != allowed[branch]:
            return {}
        expected = ('Independentphysical' + branch.replace('-', '_') +
            ' sweep, fixedreviewedhillcrest/movingfireapparatus/ordinarydriver/publichighway; reasonableandprudentanddueregardunresolved.')
        if rationale != expected:
            return {}
    gap = {'commanded_following_gap', 'along_route_body_gap', 'euclidean_body_separation'}
    condition = {'ego_speed', 'commanded_speed', 'leader_speed', 'relative_speed', 'surrounding_vehicle_count',
                 'road_grade', 'road_curvature', 'wet_road', 'ice_or_snow', 'precipitation', 'visibility_distance',
                 'native_fog_density', 'native_precipitation_strength', 'observed_tire_friction',
                 'commanded_leader_speed_drop', 'fog_setting', 'precipitation_setting', 'additional_vehicle_count', 'road_friction_setting'}
    return {name: [(phrase, 'definition.rationale')] for names, phrase in
            [(gap, 'reasonable and prudent'), (condition, 'having due regard')]
            if phrase in phrases for name in names}


def _turn_reference_selection(definition, metadata):
    """The reviewed turning-position references select physical evidence, no onset."""
    law = definition.get('target_law_id')
    contracts = {
        'NRS-484B-400-2a': ('C329610-400-2a-approach-pair',
            ['The approach for a left turn', 'that portion of the right half of the highway nearest the centerline thereof'], 'approach'),
        'NRS-484B-400-2b': ('C329610-400-2b-exit-pair',
            ['leave the intersection', 'to the right of the centerline'], 'entered')}
    if law not in contracts:
        return None
    pair, expected_phrases, reference = contracts[law]
    channels = definition.get('recording_description', {}).get('channels', [])
    trajectory = [(i,c) for i,c in enumerate(channels) if isinstance(c,dict) and c.get('name') == 'ego_trajectory']
    review = definition.get('current_legal_review_definition', {})
    variables = definition.get('variable_assignments', {})
    approach = variables.get('approach_highway_geometry', {}).get('value', {})
    entered = variables.get('entered_highway_centerline', {}).get('value', {})
    effective = definition.get('current_effective_intersection', {})
    if (definition.get('paired_probe_id') != pair
            or definition.get('probe', {}).get('primary_variable') != 'commanded_turn_path'
            or set(_phrases(definition,metadata)) != set(expected_phrases)
            or review.get('added_reviewed_legal_phrases_not_claimed_capture_authored') != expected_phrases
            or review.get('physical_case_config_and_observations_unchanged') is not True
            or approach.get('centerline') != 'y=0' or entered.get('centerline') != 'x=0'
            or not effective.get('user_approval') or len(trajectory) != 1
            or 'signed centerline offsets' not in trajectory[0][1].get('method','')
            or 'without substituting road projection for footprint' not in trajectory[0][1].get('method','')):
        return None
    path = 'definition.recording_description.channels[' + str(trajectory[0][0]) + ']'
    specs = []
    quantities = [('kin.position','m','ego_trajectory'),('kin.speed','m/s','ego_speed'),
        ('heading_authored_degrees','degrees','ego_trajectory'),
        ('signed_highway_centerline_offset','m','ego_trajectory'),
        ('footprint_highway_lateral_interval','m','ego_trajectory'),
        ('intersection_footprint_overlap_area','m^2','ego_trajectory')]
    for phrase in _phrases(definition,metadata):
        for quantity,unit,variable in quantities:
            spec = {'observable':quantity,'unit':unit,'road_user':'subject','phrase':phrase,
                'authored_paths':[path,'definition.current_legal_review_definition.interpretations'],
                'source_variables':[variable],'statistic':'instant'}
            if not quantity.startswith('kin.'):
                spec['turn_reference'] = {'highway':reference,
                    'axis':'y' if reference == 'approach' else 'x', 'coordinate_m':0.,
                    'intersection_region':effective.get('region_id'),
                    'intersection_boundary':effective.get('intersection_boundary'),
                    'position_reference':'original native actor origin; authored x east/y north',
                    'footprint_reference':'original transformed eight-corner XY hull; no road projection'}
            specs.append(spec)
    return {'specs':specs,'unresolved':[],
        'source_channels':[{'name':c.get('name'),'authored_path':'definition.recording_description.channels['+str(i)+']',
            'channel':dict(c),'status':'supporting_channel_not_independent_target_quantity'} for i,c in enumerate(channels) if isinstance(c,dict)],
        'authored_context':[{'name':n,'authored_path':'definition.variable_assignments.'+n,
            'authored_value':v.get('value'),'status':'authored_context_not_a_measurement'} for n,v in variables.items() if isinstance(v,dict) and v.get('kind')=='world_setup'],
        'intentionally_varied':['commanded_turn_path'],
        'controller_settings':[{'name':n,'authored_value':v.get('value'),'intentionally_varied':n=='commanded_turn_path',
            'status':'requested_setting_not_a_measurement'} for n,v in variables.items() if isinstance(v,dict) and v.get('kind')=='controller']}


def _stopping_reference_selection(definition, metadata):
    """Source-declared physical stop-reference/traffic histories, no hazard rule."""
    phrases = _phrases(definition,metadata)
    variables = definition.get('variable_assignments', {})
    channels = definition.get('recording_description', {}).get('channels', [])
    names = {c.get('name') for c in channels if isinstance(c,dict)}
    if (definition.get('target_law_id') != 'NRS-484B-257-1'
            or definition.get('paired_probe_id') != 'C111325-257-1-stopping-reference-v1'
            or definition.get('probe',{}).get('primary_variable') != 'stopping_reference_geometry'
            or definition.get('rationale') != 'Physical stopping-reference category under supplied257-1; no legal compliance or judgment threshold is assigned.'
            or set(phrases) != {'immediate hazard','yield the right-of-way'}
            or set(definition.get('unresolved_judgment_calls',[])) != set(phrases)
            or not {'participant_native_state','stopping_motion_history','participant_interaction_history','stopping_reference_geometry','place_sight_distance'} <= names
            or 'All traffic hazard/yielding/right-of-way/lawful progression judgments remain unresolved.' not in definition.get('recording_description',{}).get('limitations',[])):
        return None
    roles = variables.get('participant_configuration',{}).get('value',{}).get('roles',[])
    if roles != ['ego','initial_through','further_through']:
        return None
    branch = variables.get('stopping_reference_geometry',{}).get('value',{}).get('branch')
    specs=[]
    quantities=[('kin.position','m',r,'participant_native_state')for r in roles]
    quantities += [('kin.speed','m/s',r,'participant_native_state')for r in roles]
    quantities += [('intersection_footprint_overlap_area','m^2',r,'intersection_occupancy')for r in roles]
    quantities += [('through_front_entry_distance','m',r,'participant_interaction_history')for r in roles[1:]]
    quantities += [('stop_reference_front_signed_distance','m','ego','stopping_motion_history'),
        ('stop_reference_coordinate','m','ego','stopping_reference_geometry'),
        ('stop_reference_kind','categorical','ego','stopping_reference_geometry'),
        ('modeled_driver_reference_position','m','ego','driver_viewpoint_visibility'),
        ('sampled_model_place_horizon','m','ego','place_sight_distance')]
    for phrase in phrases:
        for quantity,unit,role,channel in quantities:
            specs.append({'observable':quantity,'unit':unit,'road_user':'subject' if role=='ego' else {'source_role':role,'requires_source_binding':True},
                'phrase':phrase,'authored_paths':['definition.recording_description.channels['+str(next(i for i,c in enumerate(channels)if c.get('name')==channel))+']','definition.recording_description.limitations','definition.rationale'],
                'source_variables':[channel]+(['reference_front_margin_request']if quantity=='stop_reference_front_signed_distance'else[]),'statistic':'instant','stopping_reference':{'role':role,'branch':branch,
                    'reference':'original Native reference/body geometry; no legal stop, hazard, yielding or perception predicate'}})
    return {'specs':specs,'unresolved':[],
        'source_channels':[{'name':c.get('name'),'authored_path':'definition.recording_description.channels['+str(i)+']','channel':dict(c),'status':'supporting_channel_not_independent_target_quantity'}for i,c in enumerate(channels)],
        'authored_context':[{'name':n,'authored_path':'definition.variable_assignments.'+n,'authored_value':v.get('value'),'status':'authored_context_not_a_measurement'}for n,v in variables.items()if isinstance(v,dict)and v.get('kind')=='world_setup'],
        'intentionally_varied':list(dict.fromkeys(definition.get('deliberate_differences',[])+['stopping_reference_geometry'])),'controller_settings':[{'name':n,'authored_value':v.get('value'),'intentionally_varied':n in definition.get('deliberate_differences',[]),'status':'requested_setting_not_a_measurement'}for n,v in variables.items()if isinstance(v,dict)and v.get('kind')=='controller']}


def _caravan_selection(definition, metadata):
    """Reviewed physical spaces and motion context, never sufficiency or danger."""
    if (definition.get('target_law_id')!='NRS-484B-127-3'
            or not isinstance(definition.get('rationale'),str)
            or not definition.get('rationale')
            or (definition.get('paired_probe_id')=='C228508-127-3-consecutive-spacing-v5' and definition.get('rationale')!='Unlabeled physical consecutive-spacing sampling; both spaces vary together as one declared group setting; speed requests/controller identical, actual speed histories remain observations')
            or set(_phrases(definition,metadata))!={'sufficient space','without danger'}):
        return None
    variables=definition.get('variable_assignments',{})
    group=variables.get('caravan_membership',{}).get('value',{})
    if group.get('members')!=['front','ego','rear'] or group.get('ordering_front_to_rear')!=['front','ego','rear']:
        return None
    channels=definition.get('recording_description',{}).get('channels',[])
    by_name={c.get('name'):(i,c)for i,c in enumerate(channels)if isinstance(c,dict)}
    if not {'front_group_clear_gap_m','rear_group_clear_gap_m','ego_speed','participant_motion','occupied_body_extents','consecutive_group_spaces'}<=set(by_name):
        return None
    for name in ('front_group_clear_gap_m','rear_group_clear_gap_m'):
        if by_name[name][1].get('method') not in {'All8 native body-vertex extrema on flat native +X route; full paired gaps retained independently','All8 Native body extrema along flat3D route; every paired space retained, with outsider occupancy separately recorded'}:return None
    limits=definition.get('recording_description',{}).get('limitations',[])
    limitation='Sufficient space and without danger remain uninterpreted; contact-free motion is engineering evidence only.'
    if limitation not in limits:return None
    source_uncertainty=[by_name['front_group_clear_gap_m'][1]['uncertainty'],limitation]
    specs=[]
    def add(quantity,unit,role,phrase,names,channel,predecessor=None,component=None):
        paths=['definition.recording_description.channels['+str(by_name[channel][0])+']',
               'definition.rationale','definition.unresolved_judgment_calls']
        record={'observable':quantity,'unit':unit,'road_user':{'source_role':('independent_outsider'if role=='outsider'else'caravan_'+role),'requires_source_binding':True},
            'phrase':phrase,'source_variables':[n for n in names if n in variables or n in by_name],'authored_paths':paths,'statistic':'instant',
            'caravan_source':{'role':role},'source_uncertainty':source_uncertainty,
            'association_basis':'Named consecutive spaces ground sufficient space; authored participant motion/body context accompanies the explicitly uninterpreted without-danger standard. No legal operationalization or verdict.'}
        if predecessor:record['caravan_source']['predecessor']=predecessor
        if component:record['component']=component
        specs.append(record)
    add('front_group_clear_gap_m','m','ego','sufficient space',['front_group_clear_gap_m','consecutive_gap_target_m'],'front_group_clear_gap_m','front')
    add('rear_group_clear_gap_m','m','rear','sufficient space',['rear_group_clear_gap_m','consecutive_gap_target_m'],'rear_group_clear_gap_m','ego')
    for role in ('front','ego','rear'):
        add('kin.speed','m/s',role,'without danger',['ego_speed']if role=='ego'else['participant_motion'],'ego_speed'if role=='ego'else'participant_motion')
        add('kin.extent','m',role,'without danger',['occupied_body_extents'],'occupied_body_extents',component='width')
    if 'non_group_vehicle_count'in by_name:
        if by_name['non_group_vehicle_count'][1].get('method')!='Actual complete native vehicle inventory excluding the three independently identified caravan members; outsiders never become members by common speed or lane occupancy':return None
        add('non_group_vehicle_count','1','ego','without danger',['non_group_vehicle_count'],'non_group_vehicle_count')
        add('kin.speed','m/s','outsider','without danger',['participant_motion'],'participant_motion')
        for component in ('length','width','height'):
            name='entrant_body_'+component+'_m'
            if name in by_name:
                method=by_name[name][1].get('method','')
                if not (method.startswith('Actual Native outsider local bounding-box '+component+' from twice its observed extent;')or method=='Twice the corresponding recorded actual outsider native_box_extent_m component; source native local vertices retained independently. No control or world mutation.'):return None
                add(name,'m','outsider','without danger',[name],name,component=component)
        if 'entrant_body_width_m'not in by_name:add('kin.extent','m','outsider','without danger',['occupied_body_extents'],'occupied_body_extents',component='width')
    return {'specs':specs,'unresolved':[],
        'source_channels':[{'name':c['name'],'authored_path':'definition.recording_description.channels['+str(i)+']','channel':dict(c),'source_variable_declared':c['name']in variables}for i,c in enumerate(channels)if c['name']not in ('ego_speed','front_group_clear_gap_m','rear_group_clear_gap_m')],
        'authored_context':[{'name':n,'authored_path':'definition.variable_assignments.'+n,'authored_value':v.get('value'),'status':'authored_context_not_a_measurement'}for n,v in variables.items()if isinstance(v,dict)and v.get('kind')=='world_setup'],
        'intentionally_varied':list(definition.get('deliberate_differences',[])),
        'controller_settings':[{'name':n,'authored_value':v.get('value'),'intentionally_varied':n in definition.get('deliberate_differences',[]),'status':'requested_setting_not_a_measurement'}for n,v in variables.items()if isinstance(v,dict)and v.get('kind')=='controller']}

def _post_motion_selection(definition, metadata):
    """Recorded post-motion physics under the author's joint unresolved terms."""
    phrases=_phrases(definition,metadata)
    variables=definition.get('variable_assignments',{})
    channels=definition.get('recording_description',{}).get('channels',[])
    roles=variables.get('participant_configuration',{}).get('value',{}).get('roles',[])
    if (definition.get('target_law_id')!='NRS-484B-257-2'
            or definition.get('rationale')!={
                'C111325-257-2-post-motion-v1':'Isolated subsequent-motion request, all hazard/caution/yielding judgments unresolved',
                'C111325-257-2-stopping-reference-v1':'Physical stopping-reference condition; no legal verdict or judgment threshold assigned',
                'C111325-257-2-counterpart-phase-v4':'Occupied versus two distinct approaching phases of counterpart not stop/yield sign obligated; no judgment cutoff',
                'C111325-257-2-stop-action-v1':'Isolated requested stop versus rolling action; all traffic judgments remain unresolved'
            }.get(definition.get('paired_probe_id'))
            or set(phrases)!={'immediate hazard','proceed cautiously','yielding to vehicles not so obligated to stop or yield'}
            or roles!=['ego','initial_crossing','further_crossing']):
        return None
    required={'participant_native_state','participant_interaction_history','intersection_occupancy','stopping_motion_history','driver_viewpoint_visibility','ego_speed'}
    if not required<={c.get('name')for c in channels}:return None
    branch=variables.get('stopping_reference_geometry',{}).get('value',{}).get('branch')
    if not isinstance(branch,str)or not branch:return None
    quantities=[('kin.position','m',r,'participant_native_state')for r in roles]
    quantities += [('kin.speed','m/s',r,'ego_speed'if r=='ego'else'participant_native_state')for r in roles]
    quantities += [('intersection_footprint_overlap_area','m^2',r,'intersection_occupancy')for r in roles]
    quantities += [('counterpart_front_entry_distance','m',r,'participant_interaction_history')for r in roles[1:]]
    obligations=variables.get('participant_configuration',{}).get('value',{}).get('initial_route_obligations',{})
    policy=variables.get('commanded_turn_path',{}).get('value',{}).get('event_policy','')
    scope=variables.get('governing_context',{}).get('value',{}).get('counterpart_obligation_scope','')
    if not isinstance(scope,str)or not scope.startswith('Not subject to the selected entrance stop/yield obligation')or any(obligations.get(r)!='No stop/yield sign obligation'for r in roles[1:])or not all(t in policy for t in ('subject progresses after initial full body clears','further brakes during subject crossing')):
        return None
    specs=[]
    for phrase in phrases:
        for quantity,unit,role,channel in quantities:
            caution=quantity=='kin.speed'and role=='ego'
            if (phrase=='proceed cautiously')!=caution:continue
            paths=['definition.rationale']+['definition.recording_description.channels['+str(i)+']'for i,c in enumerate(channels)if c.get('name')==channel]
            if not caution:paths.extend(['definition.variable_assignments.commanded_turn_path.value.event_policy','definition.variable_assignments.participant_configuration.value.initial_route_obligations','definition.variable_assignments.governing_context.value.counterpart_obligation_scope'])
            if channel in variables:paths.append('definition.variable_assignments.'+channel)
            source_variables=[channel]
            if quantity=='kin.speed'and role=='ego':source_variables.append('post_stop_speed_request');paths.append('definition.probe.primary_variable')
            specs.append({'observable':quantity,'unit':unit,'road_user':'subject'if role=='ego'else{'source_role':role,'requires_source_binding':True},'phrase':phrase,'authored_paths':paths,'source_variables':source_variables,'statistic':'instant',
                'stopping_reference':{'role':role,'branch':branch,'reference':'original Native marked-reference and observed crossing actors; no legal stop, hazard, caution or yielding predicate'}})
    # The authored driver-view channel concerns actual counterpart visibility;
    # physical reference category is exposed through existing region geometry.
    for phrase in phrases:
        for kind in ('stop_line','crosswalk'):
            specs.append({'observable':'st.region_geometry','unit':'m','road_user':'subject','phrase':phrase,'source_variables':['stopping_reference_geometry'],'authored_paths':['definition.variable_assignments.stopping_reference_geometry','definition.rationale'],'region_kind':kind,'component':'boundary','optional_region_kind':True})
        if phrase!='proceed cautiously':
            for other in roles[1:]:
                specs.append({'observable':'rel.visible','unit':'Boolean','road_user':'subject','phrase':phrase,'source_variables':['driver_viewpoint_visibility'],'authored_paths':['definition.recording_description.channels','definition.rationale'],'other_role':other})
    return {'specs':specs,'unresolved':[],
        'source_channels':[{'name':c.get('name'),'authored_path':'definition.recording_description.channels['+str(i)+']','channel':dict(c),'status':'supporting_channel_not_independent_target_quantity'}for i,c in enumerate(channels)],
        'authored_context':[{'name':n,'authored_path':'definition.variable_assignments.'+n,'authored_value':v.get('value'),'status':'authored_context_not_a_measurement'}for n,v in variables.items()if isinstance(v,dict)and v.get('kind')=='world_setup'],
        'intentionally_varied':list(definition.get('deliberate_differences',[])),
        'controller_settings':[{'name':n,'authored_value':v.get('value'),'intentionally_varied':n in definition.get('deliberate_differences',[]),'status':'requested_setting_not_a_measurement'}for n,v in variables.items()if isinstance(v,dict)and v.get('kind')=='controller']}


def _signal_selection(definition,metadata):
    rationales={'C245490-223-1b-appropriate-signal':'Frozen physical API indicator-onset coverage with fixed actual lane-change motion and engineering annotation; appropriateness remains unresolved.',
        'C144550-223-1b-training-range-signal-v1':'Unlabeled physical indicator lead-distance coverage on the fixed Tesla lane-change path, retaining the exact original judgment reference and measurement; complete required training/test regions from original records, not a legal standard.'}
    if (definition.get('target_law_id')!='NRS-484B-223-1b' or definition.get('paired_probe_id')not in rationales
            or definition.get('rationale')!=rationales[definition.get('paired_probe_id')]
            or 'appropriate turn signal'not in _phrases(definition,metadata)):
        return None
    channels=definition.get('recording_description',{}).get('channels',[]);by_name={c.get('name'):(i,c)for i,c in enumerate(channels)if isinstance(c,dict)}
    method='Planar original-pose path integral from first reported sole-left API state to first center lateral displacement exceeding 0.05 m; upper sampled event times, original bracketing samples retained'
    if not {'ego_turn_indicator','ego_trajectory','ego_course_change','ego_signal_lead_distance','ego_speed'}<=set(by_name)or by_name['ego_signal_lead_distance'][1].get('method')!=method:return None
    specs=[]
    for quantity,unit,channel,event in [('reported_API_turn_indicator','categorical','ego_turn_indicator',False),('original_actor_speed_mph','mph','ego_speed',False),('reported_API_signal_to_engineering_departure_path_m','m','ego_signal_lead_distance',True)]:
        record={'observable':quantity,'unit':unit,'road_user':{'source_role':'original_subject','requires_source_binding':True},'phrase':'appropriate turn signal','source_variables':[channel],
            'authored_paths':['definition.rationale','definition.recording_description.channels['+str(by_name[channel][0])+']','definition.deliberate_differences'],
            'statistic':'instant','signal_source':True,'source_uncertainty':[by_name[channel][1].get('uncertainty','Unknown total error')],
            'association_basis':'Exact authored API-onset coverage rationale leaves appropriateness unresolved; API state, actual speed and engineering-event path describe that coverage, not emitted light or a legal onset. No association to driver mental ascertainment is inferred.'}
        if event:record.update(event_source={'method':'original_API_to_engineering_departure_path','path':'evidence/ego_signal_lead_distance.jsonl'},signal_event=True)
        specs.append(record)
    variables=definition.get('variable_assignments',{})
    return {'specs':specs,'unresolved':[],'source_channels':[{'name':c['name'],'authored_path':'definition.recording_description.channels['+str(i)+']','channel':dict(c)}for i,c in enumerate(channels)if c['name']not in ('ego_turn_indicator','ego_speed','ego_signal_lead_distance')],
        'authored_context':[{'name':n,'authored_path':'definition.variable_assignments.'+n,'authored_value':v.get('value'),'status':'authored_context_not_a_measurement'}for n,v in variables.items()if isinstance(v,dict)and v.get('kind')=='world_setup'],
        'intentionally_varied':list(definition.get('deliberate_differences',[])),
        'controller_settings':[{'name':n,'authored_value':v.get('value'),'status':'requested_setting_not_a_measurement','intentionally_varied':n in definition.get('deliberate_differences',[])}for n,v in variables.items()if isinstance(v,dict)and v.get('kind')=='controller']}

def _stopping_encounter_selection(definition, metadata):
    pairs={'C111325-257-1-stop-action-v1':('stop_action_speed_request','Two physical requested-action endpoints isolate complete cessation versus slow rolling while all traffic judgments remain unresolved; no compliance or hazard threshold'),
        'C111325-257-1-through-traffic-phase-v1':('through_position_request','Already fully occupied versus two distinct positive approach positions; finite physical phase samples, no legal hazard boundary')}
    pair=definition.get('paired_probe_id');phrases=_phrases(definition,metadata);variables=definition.get('variable_assignments',{});channels=definition.get('recording_description',{}).get('channels',[])
    if pair not in pairs or definition.get('target_law_id')!='NRS-484B-257-1':return None
    primary,rationale=pairs[pair];roles=variables.get('participant_configuration',{}).get('value',{}).get('roles',[])
    if definition.get('probe',{}).get('primary_variable')!=primary or definition.get('rationale')!=rationale or set(phrases)!={'immediate hazard','yield the right-of-way'}or roles!=['ego','initial_through','further_through']:return None
    if not {'participant_native_state','participant_interaction_history','intersection_occupancy','stopping_motion_history'}<={c.get('name')for c in channels}:return None
    quantities=[('kin.position','m',r)for r in roles]+[('kin.speed','m/s',r)for r in roles]+[('intersection_footprint_overlap_area','m^2',r)for r in roles]+[('through_front_entry_distance','m',r)for r in roles[1:]]+[('native_counterpart_center_station','m','initial_through')]
    specs=[]
    for phrase in phrases:
        for quantity,unit,role in quantities:
            channel='through_vehicle_center_station'if quantity=='native_counterpart_center_station'else'intersection_occupancy'if quantity=='intersection_footprint_overlap_area'else'participant_interaction_history'if quantity=='through_front_entry_distance'else'participant_native_state'
            paths=['definition.rationale','definition.probe.primary_variable']+['definition.recording_description.channels['+str(i)+']'for i,c in enumerate(channels)if c.get('name')==channel]
            specs.append({'observable':quantity,'unit':unit,'road_user':'subject'if role=='ego'else{'source_role':role,'requires_source_binding':True},'phrase':phrase,'authored_paths':paths,'source_variables':[channel]+([primary]if(quantity=='kin.speed'and role=='ego'and primary=='stop_action_speed_request')or(quantity=='kin.position'and role=='initial_through'and primary=='through_position_request')else[]),'statistic':'instant','stopping_reference':{'role':role,'encounter_only':True,'reference':'original Native participant encounter and matched approved intersection; no unselected stop-reference or model-place inputs'}})
    return {'specs':specs,'unresolved':[],'source_channels':[{'name':c.get('name'),'authored_path':'definition.recording_description.channels['+str(i)+']','channel':dict(c),'status':'supporting_channel_not_independent_target_quantity'}for i,c in enumerate(channels)],'authored_context':[{'name':n,'authored_path':'definition.variable_assignments.'+n,'authored_value':v.get('value'),'status':'authored_context_not_a_measurement'}for n,v in variables.items()if isinstance(v,dict)and v.get('kind')=='world_setup'],'intentionally_varied':list(definition.get('deliberate_differences',[])),'controller_settings':[{'name':n,'authored_value':v.get('value'),'intentionally_varied':n in definition.get('deliberate_differences',[]),'status':'requested_setting_not_a_measurement'}for n,v in variables.items()if isinstance(v,dict)and v.get('kind')=='controller']}

def _yield_history_selection(definition,metadata):
    case=definition.get('case_id','');variants=('approaching_phase_probe','later_history_probe');phrases=_phrases(definition,metadata);channels=definition.get('recording_description',{}).get('channels',[]);variables=definition.get('variable_assignments',{})
    if definition.get('target_law_id')!='NRS-484B-257-1'or not any(case=='testing__C158208__NRS-484B-257-1__motor_vehicle_driver__'+v and definition.get('rationale')=='Measure yield nearest_view '+v+' through startup, initial response and all across-or-within interaction history.'for v in variants):return None
    if set(phrases)!={'continuous nearest visible point','immediate hazard','yielding and cautious proceeding'}or len(channels)!=1 or channels[0].get('name')!='kin.speed'or channels[0].get('method')!='Original Native ego velocity norm and full-body/through actor history'or variables.get('through_vehicle',{}).get('value')!='north approach'or variables.get('west_entrance_control',{}).get('value')!='yield_sign':return None
    paths=['definition.rationale','definition.recording_description.channels[0]','definition.variable_assignments.through_vehicle'];specs=[]
    groups={p:[(q,u,r)for r in ('ego','through')for q,u in [('kin.speed','m/s'),('kin.position','m'),('intersection_footprint_overlap_area','m^2')]]for p in ('immediate hazard','yielding and cautious proceeding')}
    groups['yielding and cautious proceeding'].append(('original_native_velocity_norm','m/s','ego'))
    groups['continuous nearest visible point']=[('original_subject_actor_position','m','ego')]
    for phrase in phrases:
        for q,unit,role in groups[phrase]:specs.append({'observable':q,'unit':unit,'road_user':'subject'if role=='ego'else{'source_role':role,'requires_source_binding':True},'phrase':phrase,'authored_paths':paths,'source_variables':['kin.speed'],'statistic':'instant','yield_history':{'role':role,'reference':'Observed full-body traffic encounter and original reference-position history; no hazard or continuous-visibility predicate'}})
    return {'specs':specs,'unresolved':[],'source_channels':[{'name':'kin.speed','channel':channels[0],'authored_path':'definition.recording_description.channels[0]','status':'original_3D_norm_and_full_body_history_support_current_horizontal_motion_separately'}],'authored_context':[{'name':n,'authored_value':v.get('value'),'authored_path':'definition.variable_assignments.'+n,'status':'authored_context_not_a_measurement'}for n,v in variables.items()],'intentionally_varied':[],'controller_settings':[]}


def _worker_speed_selection(definition, metadata):
    """Authored standalone speed/weather/traffic comparisons, not a law-wide list."""
    import re
    if definition.get('target_law_id')!='NRS-484B-600-1a':return None
    match=re.fullmatch(r'Controlled (reference|faster|rain|wet_surface|fog|nearer_traffic|narrower) condition; no reasonable/proper speed verdict\.',definition.get('rationale',''))
    channels=definition.get('recording_description',{}).get('channels',[])
    paths={c.get('name'):'definition.recording_description.channels['+str(i)+']'for i,c in enumerate(channels)}
    variables=definition.get('variable_assignments',{})
    if not match or not {'original_motion','native_geometry','environment_history'}<=set(paths) or variables.get('requested_speed_mps',{}).get('kind')!='controller':return None
    phrases=_phrases(definition,metadata)
    if not {'reasonable or proper','due regard','sight adequacy'}<=set(phrases):return None
    specs=[]
    def add(quantity,phrase,channel,role='subject',**scope):
        specs.append({'observable':quantity,'unit':None,'road_user':role,'phrase':phrase,
            'authored_paths':['definition.rationale','definition.target_law_id',paths[channel]],
            'source_variables':[channel],'statistic':'instant',**scope})
    add('kin.speed','reasonable or proper','original_motion')
    specs[-1]['source_variables'].append('requested_speed_mps')
    specs[-1]['authored_paths'].append('definition.variable_assignments.requested_speed_mps')
    other={'source_role':'other_traffic_600_1a','requires_source_binding':True}
    for role in ('subject',other):
        for quantity in ('kin.position','kin.heading','kin.extent','kin.speed'):
            add(quantity,'due regard','original_motion',role)
    add('rel.surface_gap','due regard','original_motion',other_role='other_traffic_600_1a')
    add('st.lane_width','due regard','native_geometry')
    for quantity in ('env.visibility','env.precipitation','env.wet_road','env.ice_or_snow'):
        add(quantity,'due regard','environment_history')
    add('st.sight_distance','sight adequacy','original_motion',region_kind='roadway')
    return {'specs':specs,'unresolved':[],
        'source_channels':[{'name':c.get('name'),'authored_path':paths[c.get('name')],
             'status':'supporting_source_channel_not_independent_quantity'}for c in channels],
        'authored_context':[{'name':n,'authored_value':v.get('value'),
             'authored_path':'definition.variable_assignments.'+n,'status':'authored_context_not_a_measurement'}
             for n,v in variables.items()if isinstance(v,dict)and v.get('kind')=='world_setup']+
             [{'name':p,'status':'source_reference_without_requested_physical_quantity',
               'reason':'Preserved authored source caveat; not a speed/traffic/weather quantity or a selected legal standard'}
              for p in phrases if p not in('reasonable or proper','due regard','sight adequacy')],
        'intentionally_varied':[match.group(1)],
        'controller_settings':[{'name':'requested_speed_mps','authored_value':variables['requested_speed_mps'].get('value'),
             'intentionally_varied':match.group(1)=='faster','status':'requested_setting_not_a_measurement'}]}


def _authored_observables(definition, metadata):
    """Return selected realized quantities and explicit unresolved mapping issues.

    Internal descriptors identify authored observables; public requests are selected
    below exclusively from the current ontology atom catalogue.
    No source requests or source values are copied into measurement values.
    """
    worker_speed = _worker_speed_selection(definition, metadata)
    if worker_speed is not None:return worker_speed
    opposing_turn = opposing_turn_selection(definition, metadata)
    if opposing_turn is not None:return opposing_turn
    entry_timing = entry_timing_selection(definition, metadata)
    if entry_timing is not None:return entry_timing
    yield_history = _yield_history_selection(definition, metadata)
    if yield_history is not None:return yield_history
    encounter = _stopping_encounter_selection(definition, metadata)
    if encounter is not None:
        return encounter
    post_motion = _post_motion_selection(definition, metadata)
    if post_motion is not None:
        return post_motion
    signal = _signal_selection(definition,metadata)
    if signal is not None:return signal
    stopping = _stopping_reference_selection(definition, metadata)
    if stopping is not None:
        return stopping
    caravan = _caravan_selection(definition,metadata)
    if caravan is not None:return caravan
    turn = _turn_reference_selection(definition, metadata)
    if turn is not None:
        return turn
    specs, unresolved, source_channels, authored_context = [], [], [], []
    phrases = _phrases(definition, metadata)
    links = {}
    _associations(definition, 'definition', phrases, links)
    for name, associations in {**_shared_spacing_links(definition, phrases), **_following_1271_links(definition, phrases), **_reviewed_width_1272_links(definition, phrases), **_reviewed_1272_branch_links(definition, phrases)}.items():
        links.setdefault(name, []).extend(associations)
    variables = definition.get('variable_assignments', {})
    description = definition.get('recording_description', {})
    channels = description.get('channels', []) if isinstance(description, dict) else []
    candidates = {}
    for name, variable in variables.items():
        if not isinstance(variable, dict):
            continue
        if variable.get('kind') == 'world_setup' or name == 'ego_is_driving_or_operating':
            authored_context.append({'name': name, 'authored_path': 'definition.variable_assignments.' + name,
                'authored_value': variable.get('value'), 'status': 'authored_context_not_a_measurement'})
        if (variable.get('kind') == 'subject_behavior' and name != 'ego_is_driving_or_operating'
                or variable.get('kind') == 'world_setup' and name in _OBSERVABLES):
            candidates.setdefault(name, []).append('definition.variable_assignments.' + name)
    varied = definition.get('deliberate_differences', [])
    probe = definition.get('probe', {})
    if isinstance(probe, dict) and isinstance(probe.get('primary_variable'), str):
        varied = list(varied) + [probe['primary_variable']]
    for name in varied:
        if isinstance(name, str):
            candidates.setdefault(name, []).append('definition.deliberate_differences')
    channel_by_name = {}
    for i, channel in enumerate(channels):
        if isinstance(channel, dict) and isinstance(channel.get('name'), str):
            name = channel['name']
            channel_path = 'definition.recording_description.channels[' + str(i) + ']'
            channel_by_name[name] = channel
            is_carrier = (name.startswith('synchronized_') or name.endswith(('_evidence', '_provenance', '_record')) or name in ('participant_motion', 'participant_native_state', 'traffic_inventory', 'native_actor_inventory', 'following_controller_inputs', 'subject_passing_controller_inputs', 'subject_passing_geometry', 'original_camera_graph_body_Core_joins', 'highway_condition_history', 'roadway_condition_history', 'weather_visibility_history', 'visibility_history', 'stopping_motion_history', 'participant_interaction_history', 'intersection_occupancy', 'lane_geometry_history', 'lane_availability_history', 'entry_occupancy_geometry', 'overtaking_history'))
            if name == 'modeled_stopping_distance' and channel.get('method', '').lower().startswith('if supplied'):
                is_carrier = True
            if is_carrier and name not in _OBSERVABLES:
                source_channels.append({'name': name, 'authored_path': channel_path, 'channel': dict(channel), 'source_variable_declared': name in variables})
                if name not in varied:
                    candidates.pop(name, None)
            else:
                candidates.setdefault(name, []).append(channel_path)
    road_value = variables.get('road_geometry', {}).get('value') if isinstance(variables.get('road_geometry'), dict) else None
    if 'highway_width' in variables:
        width_paths = ['definition.variable_assignments.highway_width'] + [
            c['authored_path'] for c in source_channels if c['name'] == 'roadway_condition_history']
        for width_name in ('highway_width', 'roadway_width', 'driving_lane_width', 'left_shoulder_width', 'right_shoulder_width'):
            candidates.setdefault(width_name, []).extend(width_paths)
    if isinstance(road_value, dict) and any(road_value.get(k) for k in ('source', 'source_map', 'native_proof', 'source_map_sha256')):
        for local in ('road_grade', 'road_curvature'):
            candidates.setdefault(local, []).append('definition.variable_assignments.road_geometry')
        candidates.pop('road_geometry', None)
    branch_links=_reviewed_1272_branch_links(definition,phrases)
    if branch_links and definition.get('paired_probe_id')=='C102372-127-2-subject-passing-v2':
        candidates['leader_reference_trajectory']=['definition.variable_assignments.subject_passing_profile_enabled']
    if branch_links and definition.get('paired_probe_id')=='C102372-review-interaction-v1':
        for field in ('recorded_outsider_velocity','recorded_outsider_half_extents'):
            candidates[field]=['definition.variable_assignments.commanded_outsider_entry']
    seen = set()
    for name, paths in candidates.items():
        mapping = _OBSERVABLES.get(name)
        if branch_links:
            mapping={'same_direction_lane_count':('native_same_direction_driving_lane_count','count','subject'),
                'same_direction_available_lane_count':('native_same_direction_driving_lane_count','count','subject'),
                'subject_passing_completion_count':('native_subject_pass_return_counter','count','subject'),
                'entered_gap_vehicle_count':('native_entered_gap_vehicle_count','count','subject'),
                'subject_passing_profile_enabled':('kin.position','m','subject'),
                'leader_reference_trajectory':('kin.position','m','leader'),
                'commanded_outsider_entry':('kin.position','m','recorded_extras'),
                'recorded_outsider_velocity':('kin.velocity','m/s','recorded_extras'),
                'recorded_outsider_half_extents':('kin.extent','m','recorded_extras')}.get(name,mapping)
        if name=='lead_body_asset_width_reference_m' and _reviewed_width_1272_links(definition,phrases):
            mapping=_OBSERVABLES['lead_overall_width']
        if name in {'fog_density','observed_ego_tire_friction','additional_pedestrian_count','additional_bicycle_count','additional_animal_count','road_friction'}:
            native = {
                'fog_density': ('native_fog_density','CARLA native percent','subject'),
                'observed_ego_tire_friction': ('observed_tire_friction','dimensionless native friction parameter','subject'),
                'additional_pedestrian_count': ('native_additional_pedestrian_count','count','subject'),
                'additional_bicycle_count': ('native_additional_bicycle_count','count','subject'),
                'additional_animal_count': ('native_additional_animal_mesh_count','count','subject')}
            if name == 'road_friction' and name in varied:
                mapping = ('observed_tire_friction','dimensionless native friction parameter','subject')
            else:
                mapping = native.get(name,mapping)
            if name == 'additional_animal_count':
                unresolved.append({'source_variable':name,'reason':'physical_animal_coverage_unverified_for_registered_mesh_query',
                    'authored_paths':paths,'phrases':phrases,
                    'scope':'Native static.prop.mesh /AnimaSim/ query count is observed; physical animal absence needs positive API capability proof'})
        if name in varied:
            mapping = {
                'commanded_leader_speed_drop': ('relative_speed', 'm/s', 'subject'),
                'fog_setting': ('native_fog_density', 'CARLA percent', 'subject'),
                'precipitation_setting': ('native_precipitation_strength', 'CARLA percent', 'subject'),
                'additional_vehicle_count': ('surrounding_vehicle_count', 'count', 'subject'),
                'road_friction_setting': ('observed_tire_friction', 'native wheel tire_friction', 'subject'),
            }.get(name, mapping)
        if name in ('visibility', 'visibility_distance', 'sight_visibility_distance'):
            declared_unit = channel_by_name.get(name, {}).get('unit', '')
            if declared_unit in ('m', 'meter', 'meters', 'metres'):
                mapping = ('env.visibility', 'm', 'subject')
            elif declared_unit:
                mapping = None
        if not mapping:
            unresolved.append({'source_variable': name, 'authored_paths': paths, 'reason': 'quantity_mapping_requires_source_method', 'phrases': phrases})
            continue
        quantity, unit, role = mapping
        associations = links.get(name, [])
        if not associations and len(phrases) == 1:
            associations = [(phrases[0], 'metadata.label_record.legal_judgment.references')]
        if not associations:
            unresolved.append({'source_variable': name, 'observable': quantity, 'authored_paths': paths, 'reason': 'ambiguous_phrase_association' if phrases else 'missing_exact_judgment_phrase', 'phrases': phrases})
            continue
        channel = channel_by_name.get(name, {})
        resolved_unit = unit if unit is not None else channel.get('unit')
        if not resolved_unit:
            unresolved.append({'source_variable': name, 'observable': quantity, 'authored_paths': paths, 'reason': 'source_unit_required'})
            continue
        for phrase, association_path in associations:
            key = (quantity, role, phrase)
            if key in seen:
                previous = next(s for s in specs if (s['observable'], s['road_user'].get('source_role') if isinstance(s['road_user'], dict) else s['road_user'], s['phrase']) == key)
                previous['source_variables'].append(name)
                previous['authored_paths'].extend(paths)
                continue
            seen.add(key)
            specs.append({'observable': quantity, 'unit': resolved_unit, 'road_user': role, 'phrase': phrase, 'authored_paths': list(paths) + [association_path], 'source_variables': ['road_geometry' if name in ('road_grade', 'road_curvature') and name not in variables and name not in channel_by_name else name], 'statistic': 'instant'})
            if name in ('highway_width', 'roadway_width', 'driving_lane_width', 'left_shoulder_width', 'right_shoulder_width'):
                specs[-1]['source_variables'] = ['highway_width']
                specs[-1]['source_transform'] = 'source_width_records_at_unique_user_road_station; source-road left/right sides'
            if quantity == 'kin.extent' and role!='recorded_extras':
                specs[-1]['component'] = 'width'
                specs[-1]['source_transform'] = 'twice_recorded_half_width'
            if quantity == 'observed_stopping_displacement':
                specs[-1]['event_source'] = {'method': 'original_recorded_stopping_displacement',
                                            'path': 'evidence/observed_stopping_event.json'}
            if name == 'traffic_queue_behind':
                specs[-1]['source_transform'] = 'subject_position_paired_with_recorded_other_positions; no_queue_predicate'
            if quantity in ('st.grade', 'st.curvature'):
                specs[-1]['scope'] = 'per_user_unique_source_roadway'
            if name == 'target_lane_surface_gap':
                specs[-1]['requires_source_method'] = 'target_lane_reference_and_gap_definition'
            if quantity=='native_subject_pass_return_counter':
                specs[-1]['native_passing_reference']=True
                specs[-1]['source_transform']='recorded PassingHistory 0/1 single-reference return-counter state; not cumulative/legal passing'
            if quantity=='native_same_direction_driving_lane_count':
                specs[-1]['native_lane_reference']=True
                specs[-1]['source_transform']='original_recorded_native_driving_lane_domain_direction_count; declared no-closure context, no legal availability predicate'
            if name=='leader_reference_trajectory':
                specs[-1]['source_variables']=['subject_passing_profile_enabled','participant_motion']
                specs[-1]['source_transform']='actual named leader body-centre trajectory paired with subject motion, never a passing verdict'
            if role=='recorded_extras':
                specs[-1]['native_extra_motion']=True
                specs[-1]['source_variables']=['commanded_outsider_entry','entry_occupancy_geometry']
                specs[-1]['source_transform']='all actual original extra-actor snapshots and native IDs; no entrant/queue/danger predicate'
            if definition.get('paired_probe_id')=='C102372-review-interaction-v1'and quantity in ('native_entered_gap_vehicle_count','native_same_direction_driving_lane_count','native_subject_pass_return_counter'):
                specs[-1].pop('native_passing_reference',None);specs[-1].pop('native_lane_reference',None)
                specs[-1]['interaction_native_reference']=True
                specs[-1]['source_transform']='exact retained original interaction producer count/latch/Native-lane readback; no legal entry, passing or availability predicate'
            if role != 'subject':
                specs[-1]['road_user'] = {'source_role': role, 'requires_source_binding': True}
    return {'specs': specs, 'unresolved': unresolved, 'source_channels': source_channels,
            'authored_context': authored_context,
            'intentionally_varied': list(dict.fromkeys(v for v in varied if isinstance(v, str))),
            'controller_settings': [{'name': name, 'authored_value': variable.get('value'),
                'intentionally_varied': name in varied, 'status': 'requested_setting_not_a_measurement'}
                for name, variable in variables.items() if isinstance(variable, dict) and variable.get('kind') == 'controller']}


# Public requests contain ontology IDs only. Internal authored observables are
# source concepts, not a second supported metadata format.
def derive_specs(definition, metadata):
    from judgment_atoms import ATOMS, UNITS
    import json
    authored = _authored_observables(definition, metadata)
    requests, unsupported = [], []
    def add(record, atom, role=None, **scope):
        if atom not in ATOMS or atom not in UNITS:
            raise ValueError('Unsupported ontology measurement: '+atom)
        explicit_role = role is not None
        role = role if explicit_role else record.get('road_user', 'subject')
        if isinstance(role,dict):role=role.get('source_role')
        for key in ('stopping_reference','yield_history','caravan_source'):
            if not explicit_role and role not in ('subject','original_subject') and isinstance(record.get(key),dict):role=record[key].get('role',role)
        if role=='outsider':role='independent_outsider'
        if record.get('entry_timing_role') not in (None,'pair'):role=record['entry_timing_role']
        if record.get('opposing_turn_role'):role=record['opposing_turn_role']
        if role in ('ego','original_subject','caravan_ego'):role='subject'
        request={'quantity':atom,'unit':UNITS[atom],'actor_role':role,
            'phrase':record['phrase'],'source_variables':list(record.get('source_variables',[])),
            'authored_paths':list(record.get('authored_paths',[])),**scope}
        if record.get('source_uncertainty'):request['source_uncertainty']=record['source_uncertainty']
        requests.append(request)
    for record in authored.get('specs',[]):
        observable=record['observable']
        if observable in ATOMS:
            atom_scope={k:record[k]for k in('region_kind','region_scope','optional_region_kind','other_role')if k in record}
            if observable=='st.region_geometry':atom_scope['component']='boundary'
            # Atom values always retain the atom's full shape. In particular,
            # extent is its half-size vector and surface_gap is its pair.
            if observable=='rel.surface_gap':add(record,observable,other_role=record.get('other_role','counterpart'))
            elif observable in ('st.lane_width','st.sight_distance'):
                atom_scope.setdefault('region_scope','occupied')
                add(record,observable,**atom_scope)
            else:add(record,observable,**atom_scope)
            continue
        if observable=='reported_API_turn_indicator':add(record,'sig.turn_indicator');continue
        if observable in ('original_actor_speed_mph','original_native_velocity_norm'):
            add(record,'kin.speed');add(record,'kin.velocity');continue
        if observable=='original_subject_actor_position':add(record,'kin.position');continue
        if observable=='heading_authored_degrees':add(record,'kin.heading');continue
        if observable.startswith('entrant_body_'):add(record,'kin.extent',role='independent_outsider');continue
        if observable=='intersection_footprint_overlap_area':
            add(record,'rel.occupies',region_kind='intersection')
            add(record,'st.region_geometry',region_kind='intersection',component='boundary')
        elif observable in ('along_route_body_gap','target_lane_surface_gap'):
            add(record,'rel.surface_gap',other_role='counterpart')
            for role in ('subject','counterpart'):
                for atom in ('kin.position','kin.heading','kin.extent'):add(record,atom,role=role)
        elif observable in ('front_group_clear_gap_m','rear_group_clear_gap_m'):
            add(record,'rel.surface_gap',role='subject'if observable.startswith('front')else'rear',other_role='front'if observable.startswith('front')else'subject')
        elif observable=='relative_speed':
            add(record,'kin.speed');add(record,'kin.speed',role='counterpart')
        elif observable in ('highway_width','roadway_width','left_shoulder_width','right_shoulder_width'):
            kind='shoulder'if'shoulder'in observable else observable[:-6]
            add(record,'st.region_geometry',region_kind=kind,component='boundary')
            if kind=='roadway':add(record,'st.lane_width',region_scope='occupied')
        elif observable in ('native_fog_density','native_precipitation_strength'):
            add(record,'env.visibility'if observable=='native_fog_density'else'env.precipitation')
        elif observable in ('signed_highway_centerline_offset','footprint_highway_lateral_interval'):
            for atom in ('kin.position','kin.heading','kin.extent'):add(record,atom)
            add(record,'st.region_geometry',region_kind='highway',component='boundary')
            add(record,'st.region_geometry',region_kind='centre_line',component='boundary',optional_region_kind=True)
        elif observable in ('stop_reference_front_signed_distance','stop_reference_coordinate','stop_reference_kind','counterpart_front_entry_distance','through_front_entry_distance','opposing_boundary_relative_position'):
            for atom in ('kin.position','kin.heading','kin.extent'):add(record,atom)
            add(record,'st.region_geometry',region_kind='intersection',component='boundary')
            if observable.startswith('stop_reference'):add(record,'st.region_geometry',region_kind='stop_line',component='boundary')
        elif observable in ('observed_stopping_displacement','reported_API_signal_to_engineering_departure_path_m','intersection_entry_time','intersection_entry_time_difference','native_subject_pass_return_counter','opposing_vehicles_cleared_before_commit'):
            for atom in ('kin.time','kin.position','kin.speed'):add(record,atom)
            if observable.startswith('reported_API'):add(record,'sig.turn_indicator');add(record,'kin.path_length')
            elif observable in ('intersection_entry_time','intersection_entry_time_difference','opposing_vehicles_cleared_before_commit'):add(record,'rel.occupies',region_kind='intersection')
        elif 'count' in observable:
            # Supply typed, actually delivered participants, never an inferred
            # complete population or an invented count-valued Boolean atom.
            kind=('ru.pedestrian'if'pedestrian'in observable else'ru.bicycle'if'bicycle'in observable else'ru.motor_vehicle')
            if 'animal'not in observable:
                add(record,kind,role='all_recorded')
                add(record,'kin.position',role='all_recorded')
        unsupported.append({'authored_observable':observable,'actor_role':record.get('road_user','subject'),
            'reason':'no_equivalent_ontology_atom',
            'explanation':'Source-specific scalar/category is not renamed as a different atom. Related supported atom observations are exported separately where established.',
            'phrase':record['phrase'],'source_variables':record.get('source_variables',[]),
            'authored_paths':record.get('authored_paths',[])})
    # Keep ambiguous source associations explicit, without custom quantity keys.
    unresolved=[]
    for item in authored.get('unresolved',[]):
        item=dict(item)
        if 'observable'in item:item['authored_observable']=item.pop('observable')
        unresolved.append(item)
    unique={}
    for request in requests:
        key=json.dumps({k:v for k,v in request.items()if k not in ('source_variables','authored_paths','source_uncertainty')},sort_keys=True)
        if key in unique:
            for field in ('source_variables','authored_paths','source_uncertainty'):
                unique[key][field]=list(dict.fromkeys(unique[key].get(field,[])+request.get(field,[])))
        else:unique[key]=request
    result={k:v for k,v in authored.items()if k not in ('specs','unresolved')}
    result.update(specs=list(unique.values()),unresolved=unresolved+unsupported)
    return result
