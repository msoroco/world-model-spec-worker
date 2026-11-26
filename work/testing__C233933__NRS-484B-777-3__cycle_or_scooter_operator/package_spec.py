"""Exact C233933 four-view rider formation contract."""
AID = 'testing__C233933__NRS-484B-777-3__cycle_or_scooter_operator'
LAW = 'NRS-484B-777-3'
CELL = 'C233933'
ACTOR = 'cycle_or_scooter_operator'
CAMERA_NAMES = ('overview', 'approach', 'reference_corner', 'driver_reference')
CAMERAS = [{'name': name, 'width': 1920 if i == 0 else 1280,
            'height': 1080 if i == 0 else 720, 'fov_deg': 75,
            'pose_strategy': 'source-surveyed rider formation and exclusive-use designation'}
           for i, name in enumerate(CAMERA_NAMES)]
CHANNELS = (
    ('highway_roadway_shoulder', 'source record', 'independent highway, roadway and shoulder bounds'),
    ('occupied_surface', 'source record', 'original rider occupancy on roadway or path'),
    ('exclusive_use_designation', 'source record', 'official exclusive-use designation or its absence'),
    ('bicycle_classification', 'source record', 'qualifying human-powered bicycle and moped exclusion'),
    ('rider_identity', 'source record', 'separate ego, control and companion actor IDs'),
    ('rider_formation', 'world metres/frame', 'original longitudinal and lateral rider separation at 20 Hz'),
    ('rider_motion', 'world metres/frame', 'original rider positions and speeds'))
RECORDING = {'channels': [{'name': name, 'unit': unit, 'method': method,
                           'sampling_rate_hz': 20, 'time_window': '45-second rider formation',
                           'reference_frame': 'source-surveyed Native world and roadway',
                           'uncertainty': '0.25 m is a physical formation tolerance, not a statutory abreast cutoff'}
                          for name, unit, method in CHANNELS],
             'context_inputs': [{'name': 'reviewed_rider_site', 'unit': 'source record',
                                 'method': 'source-sealed highway, surface, bicycle and rider identity packet'}],
             'limitations': ['No invented legal abreast cutoff or persistence rule.',
                             'Mopeds are excluded from this selected bicycle construction.',
                             'Synthetic diagnostics prove software behavior only.']}
