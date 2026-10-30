"""Source-faithful diagnostic lamp flags; off stays off, never an enum claim."""

def indicator_attributes(row, cfg):
    # The original left-turn runner uses the legacy column name
    # right_indicator_api_bit for its actual LeftBlinker readback (runner143).
    value=row.get('right_indicator_api_bit')
    if type(value) is not bool:raise ValueError('Missing actual indicator API boolean')
    left=cfg.get('course')=='left_turn'
    return {'light_LeftBlinker':value if left else False,'light_RightBlinker':False if left else value}


def augment_graph(graph,row,cfg,ego_actor_id):
    attrs=indicator_attributes(row,cfg); found=[]
    for node,data in graph.nodes(data=True):
        if data.get('carla_id',data.get('entity_id'))==ego_actor_id:
            for name,value in attrs.items():
                if name in data and data[name]!=value:raise ValueError('Raw indicator conflicts with original graph lamp')
                data[name]=value
            found.append(node)
    if len(found)!=1:raise ValueError('Expected one diagnostic subject graph actor')
    return {'updated_nodes':found,'raw_api_flags':attrs,'software_fixture_only':True,'physical_acceptance_claimed':False}
