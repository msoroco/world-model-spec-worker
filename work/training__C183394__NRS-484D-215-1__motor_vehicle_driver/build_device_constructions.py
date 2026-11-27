"""Assemble exact same-shoulder oncoming/device beam pair with fallbacks."""
import hashlib
import json
from pathlib import Path

from build_constructions import DESCRIPTION


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'native'
AID = ROOT.name
CASES = ('device_dim', 'device_high')
MODULES = ('runner.py', 'beam_capture.py', 'beam_native.py', 'beam_scene.py',
           'device_scene.py', 'saved_beam.py', 'oncoming_beam.py', 'finalize.py')


def source(name):
    value = (SOURCE / name).read_text()
    if name in ('runner.py', 'beam_native.py'):
        value = value.replace('from beam_scene import ', 'from device_scene import ')
    if name == 'beam_native.py':
        value = value.replace('from math import hypot\n',
                              'from math import hypot\nimport xml.etree.ElementTree as ET\n')
        old = 'mapping = world.get_map()\n'
        new = '''mapping = world.get_map()
    signal = [item for item in ET.fromstring(mapping.to_opendrive()).findall('.//signal')
              if item.attrib.get('id') == plan['device_request']['signal_id']]
    if len(signal) != 1 or signal[0].attrib.get('name') != plan['device_request']['signal_name']:
        raise RuntimeError('Original authored device map readback differs')
    device_signal = dict(signal[0].attrib)
'''
        if old not in value:
            raise ValueError('Native map seam changed')
        value = value.replace(old, new)
        value = value.replace('"physical_verified": False}',
                              '"physical_verified": False, "device_signal": device_signal}')
    if name == 'beam_capture.py':
        old = 'not case.endswith(\n            ("__condition_a", "__condition_b"))'
        new = 'case.rsplit("__", 1)[-1] not in ("device_dim", "device_high")'
        if old not in value:
            raise ValueError('Capture case seam changed')
        value = value.replace(old, new)
        old = '"condition_a" if case.endswith("__condition_a")\n                        else "condition_b"'
        if old not in value:
            raise ValueError('Capture scene seam changed')
        value = value.replace(old, 'case.rsplit("__", 1)[-1]')
        old = '''"lighting_trigger": "night_interval",
            "original_trigger_source": "original simulator weather request and timestamp; dated Nevada sun-event review pending",
            "NRS_484D_100_review_required": True,
            "civil_time_condition_verified": False,
            "utc_clock_capture": "datetime.now(timezone.utc) sampled at each original Native tick",
            "local_site_and_sun_event_review_required": True'''
        new = '''"lighting_trigger": "official_device",
            "original_trigger_source": "original OpenDRIVE lamp-use signal readback; independent official authority and applicability review pending",
            "NRS_484D_100_review_required": True,
            "authored_device_signal": scene["device_signal"],
            "official_authority_verified": False,
            "ego_applicability_verified": False,
            "utc_clock_capture": "datetime.now(timezone.utc) sampled at each original Native tick",
            "local_site_and_sun_event_review_required": True'''
        if old not in value:
            raise ValueError('Capture trigger seam changed')
        value = value.replace(old, new)
    return value


def build():
    ids = [AID + '__' + case for case in CASES]
    for case in CASES:
        for candidate, gain in (('primary', .20), ('fallback1', .26)):
            case_id = AID + '__' + case
            config = {'selected_case_id': case_id, 'supported_case_ids': ids,
                      'cell_id': 'C183394', 'law_id': 'NRS-484D-215-1',
                      'actor': 'motor_vehicle_driver', 'candidate_id': candidate,
                      'beam_mode': 'dim_within_500' if case == 'device_dim' else 'retain_high',
                      'rate_hz': 20, 'duration_s': 30, 'acceleration_gain': gain,
                      'requested_speed_mps': 2.5, 'required_atoms': [], 'source_packets': [],
                      'cameras': ['overview', 'approach', 'driver_reference', 'reference_corner'],
                      'case': {'recording_description': DESCRIPTION},
                      'recording_description': DESCRIPTION}
            test = '''import unittest
from pathlib import Path
from runner import check
from device_scene import request, validate_request

class Offline(unittest.TestCase):
    def test_exact_device_pair(self):
        outcome = check(Path(__file__).resolve().parents[1])
        self.assertEqual(outcome['frames'], 600)
        suffix = outcome['case_id'].rsplit('__', 1)[-1]
        self.assertFalse(validate_request(request(suffix))['official_status_verified'])
'''
            files = [{'path': name, 'content': source(name)} for name in MODULES]
            files.extend([{'path': 'config.json', 'content': json.dumps(config, indent=2) + '\n'},
                          {'path': 'tests/test_offline.py', 'content': test}])
            construction = {'case_id': case_id, 'cell_id': 'C183394',
                            'law_id': 'NRS-484D-215-1', 'actor': 'motor_vehicle_driver',
                            'entrypoint': 'runner.py', 'files': files,
                            'measurement_plan': '600 original 20 Hz frames; authored device map readback and independent official authority review required',
                            'recording_description': DESCRIPTION,
                            'status': 'authored_not_physically_verified'}
            target = ROOT / 'constructions' / case / candidate / 'construction.json'
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(construction, indent=2, allow_nan=False) + '\n')
            print(case, candidate, hashlib.sha256(target.read_bytes()).hexdigest())


if __name__ == '__main__':
    build()
