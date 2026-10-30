"""Software diagnostic graph author from captured-shaped actual signal readback.

Not a runtime repair. Input raw rows must already contain actual-format state
and affected_lanes. Never substitutes controller requests or ego lane for them.
"""

def augment_graph(graph, row, context=None):
    context=context or {}
    if 'signal_actor_id' in row:
        heads=[{'actor_id':row['signal_actor_id'],'state':row.get('signal_state'),'affected_lanes':row.get('affected_lanes')}]
    else:
        heads=row.get('head_states',[])
    originals={a.get('carla_id') for _,a in graph.nodes(data=True) if a.get('sem_class')=='traffic.traffic_light'}
    added=[]
    for head in heads:
        actor=head['actor_id']; state=head.get('state')
        if actor in originals:continue
        lanes=head.get('affected_lanes')
        if lanes is None:
            record=next((h for h in context.get('installed_heads',[]) if h.get('actor_id')==actor),{})
            lanes=record.get('affected_lanes')
        if state not in ('Red','Yellow','Green','Off'):
            raise ValueError('Missing actual Native signal state')
        if not lanes or any(len(l)!=3 or any(type(v) is not int for v in l) for l in lanes):
            raise ValueError('Missing actual-format affected lane readback; cannot infer governance')
        node='diagnostic_signal_'+str(actor)
        if node in graph:raise ValueError('Diagnostic signal identity collision')
        graph.add_node(node,sem_class='traffic.traffic_light',carla_id=actor,light_state=state,
                       observed_governs=[list(l) for l in lanes],diagnostic_fixture=True,
                       diagnostic_scope='Software-authored graph from raw signal history; Native realization, visibility and authority unverified')
        added.append(node)
    return {'added_nodes':added,'software_fixture_only':True,'physical_acceptance_claimed':False}


def diagnostic_enrich2504(root, cfg):
    """Author missing legacy diagnostic metadata from explicit scene validities.

    Native runners capture API affected_lanes. These software fixtures model that
    shape from declared OpenDRIVE validities, with explicit diagnostic provenance;
    they do not establish API realization or official governance.
    """
    import hashlib
    import json
    from pathlib import Path
    import xml.etree.ElementTree as ET
    root=Path(root)
    if cfg.get('law_id')!='NRS-484B-250-4':return {'changed':False}
    diagnostic=(root/'fixture-provenance.json').exists()
    if (root/'acquisition-provenance.json').exists():diagnostic=diagnostic or json.loads((root/'acquisition-provenance.json').read_text()).get('diagnostic_fixture') is True
    if not diagnostic:raise ValueError('Diagnostic enrichment must never rewrite real capture')
    context_path=root/'signal_context.json'; context=json.loads(context_path.read_text());heads=context.get('installed_heads',[])
    history_path=root/'interaction_history.jsonl'; rows=[json.loads(s) for s in history_path.read_text().splitlines() if s]
    if cfg.get('installed_heads',True) is False:
        if heads or any(r.get('head_states') for r in rows):raise ValueError('Absent branch contradicts installed head evidence')
        return {'changed':False,'absent_preserved':True}
    scene=root/'scene.xodr'; tree=ET.parse(scene).getroot(); declarations={}
    for road in tree.findall('road'):
        for signal in road.findall('./signals/signal'):
            if signal.get('type')!='1000001':continue
            station=float(signal.attrib['s']); sections=road.findall('./lanes/laneSection'); section=max((i for i,s in enumerate(sections) if float(s.attrib['s'])<=station),default=None)
            if section is None:raise ValueError('Signal lane section absent')
            lanes=[]
            for validity in signal.findall('validity'):
                lo,hi=sorted((int(validity.attrib['fromLane']),int(validity.attrib['toLane'])))
                lanes.extend([[int(road.attrib['id']),section,l] for l in range(lo,hi+1) if l])
            if not lanes:raise ValueError('Explicit scene signal validity required')
            declarations[signal.attrib['id']]=lanes
    if len(heads)!=len(declarations):raise ValueError('Diagnostic installed head count differs from scene')
    # Legacy fixture actor IDs have no OpenDRIVE metadata. The explicit synthetic
    # association is ordered and recorded, never presented as a Native API readback.
    association={h['actor_id']:str(h.get('opendrive_id') or ident) for h,ident in zip(sorted(heads,key=lambda h:h['actor_id']),sorted(declarations,key=int))}
    provenance={'kind':'software_authored_from_explicit_scene_signal_validity','scene_sha256':hashlib.sha256(scene.read_bytes()).hexdigest(),'native_api_verified':False}
    def enrich(h):
        ident=association[h['actor_id']]
        if ident not in declarations:raise ValueError('Head identity absent from scene')
        h.setdefault('opendrive_id',ident);h.setdefault('affected_lanes',declarations[ident]);h.setdefault('diagnostic_authoring',provenance)
    for h in heads:enrich(h)
    for row in rows:
        for h in row.get('head_states',[]):enrich(h)
    context_path.write_text(json.dumps(context,indent=2)+'\n');history_path.write_text(''.join(json.dumps(r)+'\n' for r in rows))
    return {'changed':True,'association':association,'provenance':provenance}
