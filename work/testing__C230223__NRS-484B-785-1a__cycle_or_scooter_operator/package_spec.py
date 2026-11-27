"""Exact scooter lane and speed capture contract for NRS 484B.785(1)(a)."""

AID = 'testing__C230223__NRS-484B-785-1a__cycle_or_scooter_operator'
LAW = 'NRS-484B-785-1a'
CELL = 'C230223'
ACTOR = 'cycle_or_scooter_operator'
CAMERA_NAMES = ('overview', 'approach', 'reference_corner', 'driver_reference')
CAMERAS = [{'name': name, 'width': 1920 if index == 0 else 1280,
            'height': 1080 if index == 0 else 720, 'fov_deg': 75,
            'pose_strategy': 'reviewed bicycle-lane extent, scooter body and speed visibility'}
           for index, name in enumerate(CAMERA_NAMES)]
CHANNELS = (
    ('scooter_device_identity', 'source record', 'reviewed original device manufacturer and measured characteristics'),
    ('bicycle_lane_designation', 'source record', 'official lane designation and sourced polygon extent'),
    ('ego_body_lane_occupancy', 'boolean per frame', 'original Native body corner occupancy within designated polygon'),
    ('ego_speed_mph', 'miles per hour per frame', 'original Native velocity magnitude at 20 Hz'),
    ('ordinance_applicability', 'source record', 'official applicable jurisdiction, ordinance and effective date'),
    ('original_frame_join', 'frame and seconds', 'original Native frame, trace and four-camera join'))
RECORDING = {'channels': [
    {'name': name, 'unit': unit, 'method': method, 'sampling_rate_hz': 20,
     'time_window': '45 seconds including steady 10 to 40 second window',
     'reference_frame': 'original Native map, body geometry and source review',
     'uncertainty': '0.25 mph engineering target tolerance does not alter statutory 15 mph boundary'}
    for name, unit, method in CHANNELS],
    'context_inputs': [{'name': 'reviewed_scooter_site', 'unit': 'source record',
                        'method': 'sealed official lane, device, jurisdiction and ordinance packet'}],
    'limitations': ['Original speed, actual pixels and official designation require local review.',
                    'NRS 484A.469 text was not supplied; ordinance effect remains unresolved.',
                    'Synthetic diagnostics prove software behavior only.']}
