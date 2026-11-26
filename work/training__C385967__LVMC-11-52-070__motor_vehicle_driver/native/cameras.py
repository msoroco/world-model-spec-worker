"""Four synchronized views of the one-way angle bay."""
from __future__ import annotations

NAMES = ('overview', 'approach', 'reference_corner', 'driver_reference')
SIZES = ((1920, 1080), (1280, 720), (1280, 720), (1280, 720))


def check(cameras):
    if len(cameras) != 4 or tuple(item.get('name') for item in cameras) != NAMES:
        raise ValueError('Four named angle-bay source cameras required')
    for item, size in zip(cameras, SIZES):
        if (item.get('width'), item.get('height'), item.get('fps')) != (*size, 20) or \
                not item.get('pose_strategy') or not item.get('fov_deg') or \
                len(item.get('location_xyz_m', [])) != 3 or \
                len(item.get('rotation_pyr_deg', [])) != 3:
            raise ValueError('Angle-bay camera profile differs')
    return {'names': list(NAMES), 'frames': 600, 'synchronized': True}


def transform(carla, item):
    x, y, z = item['location_xyz_m']
    pitch, roll, yaw = item['rotation_pyr_deg']
    return carla.Transform(carla.Location(x=x, y=y, z=z),
                           carla.Rotation(pitch=pitch, roll=roll, yaw=yaw))
