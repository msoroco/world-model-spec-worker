"""Construct explicit software diagnostic nine-body-ray packets.

Caller must supply nine authored outcomes for EACH inventoried target. A single
center ray, missing ray, or empty inventory is never expanded into visibility.
"""
import math


def construct_relations(participants,subject_id,outcomes):
    actors={a['actor_id']:a for a in participants}
    if len(actors)!=len(participants) or subject_id not in actors:raise ValueError('Invalid subject/participant inventory')
    subject=actors[subject_id];position=subject['position_m'];eye=[position[0],position[1],position[2]+1.5]
    targets=set(actors)-{subject_id}
    if not targets or set(outcomes)!=targets:raise ValueError('Explicit full target ray inventory required; no empty-inventory visibility inference')
    relations=[]
    for actor_id in sorted(targets):
        vertices=actors[actor_id]['body_vertices_m']
        if len(vertices)!=8:raise ValueError('Eight original-format body vertices required')
        centre=[sum(v[i] for v in vertices)/8 for i in range(3)];endpoints=vertices+[centre];measurements=outcomes[actor_id]
        if len(measurements)!=9:raise ValueError('Nine explicit authored ray outcomes required')
        rays=[]
        for target,measurement in zip(endpoints,measurements):
            blockers=measurement.get('blockers');clear=measurement.get('clear')
            if type(clear) is not bool or not isinstance(blockers,list) or clear!= (not blockers):raise ValueError('Missing or inconsistent explicit diagnostic ray outcome')
            if not all(math.isfinite(x) for x in [*eye,*target]):raise ValueError('Nonfinite ray endpoint')
            rays.append({'observer_m':eye,'target_m':list(target),'blockers':blockers,'clear':clear,'diagnostic_authored':True})
        relations.append({'a':subject_id,'b':actor_id,'visible':any(r['clear'] for r in rays),'method':'any_of_nine_body_collision_rays_subject_reference_z_1.5m','rays':rays,'diagnostic_authoring':'Explicit software-constructed ray outcomes; not actual Native ray casts or physical visibility acceptance'})
    return relations


def author_packet(root,cfg,event,rawrow):
    """Explicit diagnostic vertex-visible/centre-obstructed source construction.

    The nine authored outcomes are a software test vector, never reconstructed
    Native ray casts. The raw centre obstruction remains independently retained.
    """
    import copy
    import json
    from pathlib import Path
    root=Path(root)
    diagnostic=(root/'fixture-provenance.json').is_file()
    if (root/'acquisition-provenance.json').is_file():diagnostic=diagnostic or json.loads((root/'acquisition-provenance.json').read_text()).get('diagnostic_fixture') is True
    if not diagnostic:raise ValueError('Must never author a real capture visibility packet')
    if cfg.get('law_id')!='NRS-484B-250-4':raise ValueError('Diagnostic role visibility author only supports2504')
    if rawrow.get('frame')!=event['original_frame']:raise ValueError('Raw visibility frame join failed')
    states=rawrow['states'];subject_id=event['actor_id'];original=event['original_observations']['participants']
    template=next((a for a in original if a['actor_id']==subject_id),None)
    if template is None:raise ValueError('Original subject participant template missing')
    ids={'ego':subject_id};available=(i for i in range(108,1000) if i!=subject_id)
    for role in ('earlier_stopped','inside_vehicle'):ids[role]=next(available)
    participants=[];outcomes={}
    for role in ('ego','earlier_stopped','inside_vehicle'):
        state=states[role];body=state['body_vertices_m']
        if len(body)!=8:raise ValueError('Diagnostic full eight-vertex role body required')
        actor=copy.deepcopy(template);actor_id=ids[role];actor['actor_id']=actor_id
        centre=[sum(v[i] for v in body)/8 for i in range(3)]
        if role=='ego':centre=event['ego']['position_m']
        speed=state['speed_mps'];velocity=state.get('velocity_mps',[speed,0,0])
        actor.update(position_m=list(centre),body_vertices_m=copy.deepcopy(body),speed_mps=speed,velocity_mps=velocity,heading_deg=state.get('heading_deg',event['ego'].get('heading_deg',0)))
        actor['diagnostic_role_association']={'role':role,'method':'explicit software-assigned role identity and raw full-body geometry; not Native actor readback'}
        participants.append(actor)
        if role=='ego':continue
        measurements=[{'clear':True,'blockers':[]}]+[{'clear':False,'blockers':[{'label':'diagnostic_fixture_occluder'}]} for _ in range(7)]
        if role=='earlier_stopped':
            # Preserve the actual-format source centre-ray outcome, while the
            # other eight values remain explicitly authored independent samples.
            ray=rawrow.get('sight_ray')
            if not isinstance(ray,dict) or not isinstance(ray.get('hits'),list):raise ValueError('Explicit raw centre-ray hits required')
            blockers=copy.deepcopy(ray['hits']);measurements.append({'clear':not blockers,'blockers':blockers})
        else:measurements.append({'clear':True,'blockers':[]})
        outcomes[actor_id]=measurements
    relations=construct_relations(participants,subject_id,outcomes)
    return {'participants':participants,'relations':relations,'road_user_visibility_observed':True,'software_fixture_only':True,'physical_acceptance_claimed':False}
