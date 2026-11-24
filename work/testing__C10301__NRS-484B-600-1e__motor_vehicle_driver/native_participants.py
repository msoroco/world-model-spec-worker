"""Sample live vehicle and walker body histories for the Core graph source."""
from __future__ import annotations

import math

from original_graph import _actor_node


def observe(world, ego_actor) -> list[dict]:
    actors = [actor for actor in world.get_actors()
              if getattr(actor, 'is_alive', False)
              and isinstance(getattr(actor, 'type_id', None), str)
              and actor.type_id.startswith(('vehicle.', 'walker.'))]
    ids = [actor.id for actor in actors]
    if len(ids) != len(set(ids)) or ids.count(ego_actor.id) != 1:
        raise ValueError('original Native participant identities invalid')
    records = []
    for actor in sorted(actors, key=lambda item: item.id):
        attributes = _actor_node(actor, ego=actor.id == ego_actor.id)['attributes']
        velocity = attributes['velocity_mps']
        forward = attributes['forward']
        records.append({
            'actor_id': actor.id, 'blueprint': actor.type_id,
            'position_m': attributes['vertex'],
            'velocity_mps': velocity,
            'speed_mps': math.sqrt(sum(component * component for component in velocity)),
            'heading_deg': math.degrees(math.atan2(forward[1], forward[0])),
            'body_vertices_m': attributes['threedbbox'],
            'source': 'original_live_world_actor_readback'})
    return records
