"""Verify no worker pedestrian appears in a retained Native inventory.

An empty walker inventory does not establish that no emergency business occurred.
"""


def derive(inventory_rows, ego_rows, first_stationary_frame):
    if type(first_stationary_frame) is not int or first_stationary_frame < 0 or \
       len(inventory_rows) != len(ego_rows) or not inventory_rows:
        raise ValueError('Missing synchronized business-worker inventory')
    kind = ego_rows[0].get('source_kind')
    for i, (inventory, ego) in enumerate(zip(inventory_rows, ego_rows)):
        if inventory.get('frame') != i or ego.get('frame') != i or \
           inventory.get('native_frame') != ego.get('native_frame') or \
           inventory.get('time_s') != ego.get('time_s') or \
           inventory.get('source_kind') != kind or \
           inventory.get('inventory_source') != \
               'world.get_actors().filter(walker.pedestrian.*)':
            raise ValueError('Changed business-worker inventory provenance or frame join')
        actor_ids = inventory.get('walker_actor_ids')
        if actor_ids != []:
            raise ValueError('No-worker case contains a pedestrian actor')
    return []
