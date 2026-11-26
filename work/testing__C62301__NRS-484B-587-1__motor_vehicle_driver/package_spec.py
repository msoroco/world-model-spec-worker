"""Exact controlled-access entrance and exit delivery contract."""
AID = 'testing__C62301__NRS-484B-587-1__motor_vehicle_driver'
LAW = 'NRS-484B-587-1'
CELL = 'C62301'
ACTOR = 'motor_vehicle_driver'
CAMERA_NAMES = ('overview', 'approach', 'reference_corner', 'driver_reference')
CAMERAS = [{'name': name, 'width': 1920 if i == 0 else 1280, 'height': 1080 if i == 0 else 720, 'fov_deg': 75, 'pose_strategy': 'source-surveyed highway boundary, official device and vehicle route'} for i, name in enumerate(CAMERA_NAMES)]
CHANNELS = (
 ('controlled_access_authority', 'source record', 'separate public-authority controlled-access determination'),
 ('public_highway_boundary', 'world meters', 'surveyed public highway extent and boundary'),
 ('official_erected_devices', 'source record', 'authority-designated erected official device inventory'),
 ('designated_access_points', 'source record', 'officially indicated entrance and exit windows'),
 ('notice_visibility', 'frame/source', 'original driver-view pixels plus independent notice source'),
 ('vehicle_boundary_crossing', 'world meters/frame', 'original Native vehicle pose and boundary crossing at 20 Hz'),
 ('vehicle_motion', 'world meters/frame', 'original Native position, speed and controller history'),
)
RECORDING = {'channels': [{'name': name, 'unit': unit, 'method': method, 'sampling_rate_hz': 20, 'time_window': '45-second controlled-access entry or exit', 'reference_frame': 'source-surveyed public highway boundary and Native world', 'uncertainty': 'Map road type does not establish legal controlled-access status; notice designation requires official source'} for name, unit, method in CHANNELS], 'context_inputs': [{'name': 'reviewed_controlled_access_site', 'unit': 'source record', 'method': 'sealed authority, highway boundary, official device and route packet'}], 'limitations': ['Official legal designation and authority are separately sourced.', 'Synthetic diagnostics prove software behavior only.', 'Notice visibility and crossing require original pixels and Native route readback.']}
