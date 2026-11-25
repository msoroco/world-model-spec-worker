"""CPU source-map test of original survey positive and negative branches."""
import argparse
import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from survey import inspect


class Location:
    def __init__(self, x, y, z=0):
        self.x, self.y, self.z = x, y, z


class Carla:
    Location = Location

    class LaneType:
        Driving = 1


class Waypoint:
    road_id = 1
    lane_id = -1

    def __init__(self, location):
        self.transform = type('Transform', (), {'location': location})()


class Map:
    def __init__(self, source, bad_lane=False):
        self.source, self.bad_lane = source, bad_lane

    def to_opendrive(self):
        return self.source

    def get_waypoint(self, location, **kwargs):
        waypoint = Waypoint(location)
        if self.bad_lane:
            waypoint.lane_id = -2
        return waypoint


class World:
    def __init__(self, source, bad_lane=False):
        self.mapping = Map(source, bad_lane)

    def get_map(self):
        return self.mapping

    def get_weather(self):
        return type('Weather', (), {'precipitation': 0.0, 'wetness': 0.0})()


def rejects(action, fragment):
    try:
        action()
    except ValueError as exc:
        if fragment not in str(exc):
            raise AssertionError(str(exc)) from exc
    else:
        raise AssertionError('Invalid original map was accepted')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('output')
    args = parser.parse_args()
    road = Path(__file__).with_name('road.xodr')
    source = road.read_text()
    good = inspect(World(source), Carla)
    assert good['stop_sign_signal_id'] == 901 and len(good['lane_samples']) == 3
    rejects(lambda: inspect(World(source, True), Carla), 'approach lane differs')
    root = ET.fromstring(source)
    sign = root.find('./road/signals/signal')
    sign.set('s', '200')
    changed = ET.tostring(root, encoding='unicode')
    rejects(lambda: inspect(World(changed), Carla), 'stop sign position differs')
    sign.set('name', 'YIELD')
    rejects(lambda: inspect(World(ET.tostring(root, encoding='unicode')), Carla),
            'stop sign or road geometry missing')
    receipt = {'format': 'c111325-native-bicycle-survey-cpu-v1',
               'passed': True, 'road_sha256': hashlib.sha256(road.read_bytes()).hexdigest(),
               'surveyor_sha256': hashlib.sha256(Path(__file__).with_name('survey.py').read_bytes()).hexdigest(),
               'negative_checks': 3, 'original_native_executed': False,
               'legal_prudence_verdict': None}
    Path(args.output).write_text(json.dumps(receipt, indent=2)+'\n')
    print(json.dumps({'passed': True, 'negative_checks': 3}))


if __name__ == '__main__':
    main()
