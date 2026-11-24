"""C230266 sidewalk encounter Native plan and CPU preflight.

Native capture requires a proven bicycle blueprint and a synchronized
microphone at the pedestrian. The CPU check never imports CARLA.
"""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
CAMERAS = ('overview', 'rider_approach', 'pedestrian_side', 'pass_close')


def check(config):
    if (config['cell_id'], config['law_id'], config['actor']) != (
            'C230266', 'LVMC-11-40-180-C', 'cycle_or_scooter_operator'):
        raise ValueError('Frozen assignment identity differs')
    if config['duration_s'] != 30 or config['rate_hz'] != 20:
        raise ValueError('30 second 20 Hz capture contract differs')
    if tuple(x['name'] for x in config['cameras']) != CAMERAS:
        raise ValueError('Four original source cameras required')
    if config['device_blueprint_filter'] != 'vehicle.diamondback.century':
        raise ValueError('Unreviewed replacement vehicle class')
    if config['pedestrian_microphone']['location'] != 'pedestrian_actor':
        raise ValueError('Audio must be measured at pedestrian location')
    if config['signal_frame'] is not None and not 0 <= config['signal_frame'] < 600:
        raise ValueError('Signal frame outside original capture')
    road = ET.parse(HERE/'road.xodr').getroot()
    sidewalk = road.find('.//lane[@id="-2"]')
    if sidewalk is None or sidewalk.attrib.get('type') != 'sidewalk':
        raise ValueError('Authored sidewalk lane absent')
    return {'case_id': config['case_id'], 'frames': 600,
            'cameras': list(CAMERAS), 'sidewalk_lane_id': -2,
            'rider_device_blueprint_filter': config['device_blueprint_filter'],
            'microphone_required': True, 'native_imported': False,
            'physical_and_legal_observation': False}


class RiderPolicy:
    def __init__(self, config):
        self.signal_frame = config['signal_frame']
        self.pause_window = tuple(config['pause_window_frames'])

    def request(self, frame):
        return {'forward_speed_mps': 0.0 if self.pause_window[0] <= frame < self.pause_window[1] else 1.4,
                'audible_signal_request': self.signal_frame is not None and frame == self.signal_frame}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    config = json.loads((HERE/'config.json').read_text())
    summary = check(config)
    policy = RiderPolicy(config)
    assert len([policy.request(i) for i in range(600)]) == 600
    if not args.check:
        raise RuntimeError('Native capture requires original bicycle motion and synchronized pedestrian-location microphone acquisition; this draft has no source-bound acquisition implementation')
    print(json.dumps(summary, sort_keys=True))


if __name__ == '__main__':
    main()
