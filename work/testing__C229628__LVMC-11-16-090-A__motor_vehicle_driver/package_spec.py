"""Fixed identity and source-observation recording contract for contest-aid cases."""
AID = 'testing__C229628__LVMC-11-16-090-A__motor_vehicle_driver'
LAW = 'LVMC-11-16-090-A'
CELL = 'C229628'
ACTOR = 'motor_vehicle_driver'
CAMERA_NAMES = ('overview', 'approach', 'reference_corner', 'driver_reference')
CAMERAS = [{'name': name, 'width': 1920 if index == 0 else 1280,
            'height': 1080 if index == 0 else 720, 'fov_deg': 75,
            'pose_strategy': 'source-reviewed start line, both identified motor vehicles'}
           for index, name in enumerate(CAMERA_NAMES)]
CHANNELS = (
    ('participants', 'source record', 'two persons and qualifying motor vehicles'),
    ('highway_jurisdiction', 'source record', 'municipal and highway source designations'),
    ('lane_and_route', 'Native map', 'reviewed lane marking and connected two-vehicle routes'),
    ('cue_and_episode', 'original frame', 'physical high-beam cue readback and episode context'),
    ('two_vehicle_motion', 'm/s and m/s²', 'original positions, speeds and accelerations'),
    ('camera_frame_identity', 'original frame', 'four synchronized source cameras'),
)
RECORDING = {
    'channels': [{'name': name, 'unit': unit, 'method': method,
                  'sampling_rate_hz': 20, 'time_window': '45-second aid/contest probe',
                  'reference_frame': 'source-reviewed Native start line and route',
                  'uncertainty': 'observations do not decide contest, aid or abet'}
                 for name, unit, method in CHANNELS],
    'context_inputs': [{'name': 'reviewed_native_site', 'unit': 'source record',
                        'method': 'sealed map, person, vehicle, highway and episode packet'}],
    'limitations': ['Synthetic fixtures prove software compatibility only.',
                    'The physical cue and motion are not a legal contest or aid finding.']}
