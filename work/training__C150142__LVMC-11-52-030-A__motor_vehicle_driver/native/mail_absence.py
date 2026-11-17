"""Require empty retained worker and parcel inventories during no-deposit probe.

An empty diagnostic inventory does not prove no real-world mail activity.
"""


def derive(worker_rows, parcel_rows, ego_rows, stationary_first_frame):
    if type(stationary_first_frame) is not int or stationary_first_frame < 0 or \
            not (len(worker_rows)==len(parcel_rows)==len(ego_rows)) or \
            len(ego_rows)<=stationary_first_frame:
        raise ValueError('Missing synchronized mail absence sources')
    kind=ego_rows[0].get('source_kind')
    if kind not in ('native','original_native','synthetic_native_sample'):
        raise ValueError('Invalid mail absence provenance')
    for frame,(worker,parcel,ego) in enumerate(zip(worker_rows,parcel_rows,ego_rows)):
        if any(row.get('frame')!=frame or row.get('source_kind')!=kind or
               row.get('native_frame')!=ego.get('native_frame') or
               row.get('time_s')!=ego.get('time_s')
               for row in (worker,parcel,ego)):
            raise ValueError('Changed mail absence source frame join')
        if worker.get('inventory_source')!='world.get_actors().filter(walker.pedestrian.*)' or \
                worker.get('walker_actor_ids')!=[]:
            raise ValueError('No-deposit case contains a mail worker')
        if parcel.get('inventory_source')!='world.get_actors().filter(static.prop.box*)' or \
                parcel.get('parcel_actor_ids')!=[]:
            raise ValueError('No-deposit case contains a parcel prop')
    return []
