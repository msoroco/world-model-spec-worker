"""Source cameras for a resting vehicle at the roadway edge."""

NAMES = ('overview', 'approach', 'reference_corner', 'driver_reference')
SIZES = ((1920, 1080), (1280, 720), (1280, 720), (1280, 720))


def check(cameras):
    if len(cameras) != 4 or tuple(item.get('name') for item in cameras) != NAMES:
        raise ValueError('Four named road-edge source cameras required')
    for item, size in zip(cameras, SIZES):
        if (item.get('width'), item.get('height'), item.get('fps')) != (*size, 20) or \
                item.get('pose_strategy') not in ('world_static', 'ego_follow') or \
                not item.get('fov_deg') or len(item.get('location_xyz_m', [])) != 3 or \
                len(item.get('rotation_pyr_deg', [])) != 3:
            raise ValueError('Road-edge camera profile differs')
    return {'names': list(NAMES), 'synchronized': True}


def transform(carla, item):
    x, y, z = item['location_xyz_m']
    pitch, roll, yaw = item['rotation_pyr_deg']
    return carla.Transform(carla.Location(x=x, y=y, z=z),
                           carla.Rotation(pitch=pitch, roll=roll, yaw=yaw))
