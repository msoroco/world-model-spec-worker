"""Native physical near-side crosswalk tiles adapted from accepted C111325 example."""
ASSET='/Game/Carla/Static/RoadLine/SM_BassicTrafficLineCube_trafficlineCube.SM_BassicTrafficLineCube_trafficlineCube'
EXTENT=(.06204589828848839,.06204365938901901,.0038028834387660027)
CENTER=(.061835937201976776,0,2.38418573772492e-09)
SCALE=.35/(2*EXTENT[1])

def spawn(carla,world):
    bp=world.get_blueprint_library().find('static.prop.mesh')
    bp.set_attribute('mesh_path',ASSET);bp.set_attribute('scale',str(SCALE));bp.set_attribute('mass','0')
    actors=[]
    for stripe in range(20):
        for tile in range(4):
            x=-8.275+.35*tile;y=-6.825+.7*stripe
            bp.set_attribute('role_name','C331230_near_side_crosswalk_%02d_%02d'%(stripe,tile))
            pose=carla.Transform(carla.Location(x=x-CENTER[0],y=y,z=.002-EXTENT[2]*SCALE-CENTER[2]))
            actor=world.spawn_actor(bp,pose)
            actor.set_simulate_physics(False);actor.set_collisions(False)
            actors.append(actor)
    return actors

def observe(actors):
    rows=[]
    for actor in actors:
        tr=actor.get_transform()
        rows.append({'actor_id':actor.id,'role':actor.attributes.get('role_name'),'mesh':actor.attributes.get('mesh_path'),'body_vertices_m':[[v.x,v.y,v.z] for v in actor.bounding_box.get_world_vertices(tr)]})
    return rows
