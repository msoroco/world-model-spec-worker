"""CPU validation of the authored signalized one-way approach site."""
import hashlib
import json
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
SITE = HERE / 'yellow-red-site.xodr'


def validate(path):
    path = Path(path)
    root = ET.parse(path).getroot()
    if root.tag != 'OpenDRIVE':
        raise ValueError('Expected OpenDRIVE site')
    roads = {r.get('id'): r for r in root.findall('road')}
    if set(roads) != {'158190', '158192', '158193', '158194', '158195', '158196'}:
        raise ValueError('One-way-to-two-way road topology differs')
    if any(roads[n].get('junction') != '158191' for n in ('158192', '158195')):
        raise ValueError('Intersection connector differs')
    lanes = roads['158190'].findall('./lanes/laneSection/right/lane')
    if len(lanes) != 1 or lanes[0].get('id') != '-1' or lanes[0].get('type') != 'driving':
        raise ValueError('Ego approach must be one-way driving lane -1')
    heads = roads['158190'].findall('./signals/signal')
    if len(heads) != 1:
        raise ValueError('Expected exactly one ego-facing signal head')
    head = heads[0]
    validity = head.find('validity')
    if (head.get('dynamic') != 'yes' or head.get('type') != '1000001' or
            head.get('orientation') != '+' or validity is None or
            (validity.get('fromLane'), validity.get('toLane')) != ('-1', '-1') or
            not 0 < float(head.get('s', '0')) < float(roads['158190'].get('length', '0'))):
        raise ValueError('Dynamic head does not govern the authored ego lane')
    controller = root.findall('controller')
    controls = root.findall('./controller/control')
    references = root.findall("./junction[@id='158191']/controller")
    if (len(controller) != 1 or len(controls) != 1 or len(references) != 1 or
            controls[0].get('signalId') != head.get('id') or
            references[0].get('id') != controller[0].get('id')):
        raise ValueError('Signal head lacks the intersection controller')
    return {'site_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'ego_road_id': 158190, 'ego_lane_id': -1, 'junction_id': 158191,
            'signal_id': head.get('id'), 'controller_id': controller[0].get('id')}


def select_native_governing_head(world, road_id=158190, lane_id=-1):
    """Require a unique live light whose Native affected lane is the ego lane."""
    matches = []
    for light in world.get_actors().filter('traffic.traffic_light*'):
        affected = light.get_affected_lane_waypoints()
        if any(wp.road_id == road_id and wp.lane_id == lane_id for wp in affected):
            matches.append(light)
    if len(matches) != 1:
        raise ValueError(f'Expected one Native governing head, found {len(matches)}')
    return matches[0]


def main():
    proof = validate(SITE)
    with tempfile.TemporaryDirectory(prefix='c158196-yellow-site-') as tmp:
        bad = Path(tmp) / 'bad.xodr'
        root = ET.parse(SITE).getroot()
        root.find("./road[@id='158190']/signals/signal/validity").set('fromLane', '1')
        ET.ElementTree(root).write(bad)
        try:
            validate(bad)
        except ValueError as error:
            if 'does not govern' not in str(error):
                raise
            proof['negative_wrong_lane'] = str(error)
        else:
            raise AssertionError('Wrong-lane head was accepted')
    class FakeWaypoint:
        def __init__(self, road_id, lane_id):
            self.road_id, self.lane_id = road_id, lane_id

    class FakeLight:
        def __init__(self, actor_id, lanes):
            self.id, self.lanes = actor_id, lanes

        def get_affected_lane_waypoints(self):
            return [FakeWaypoint(*lane) for lane in self.lanes]

    class FakeActors:
        def __init__(self, lights):
            self.lights = lights

        def filter(self, pattern):
            if pattern != 'traffic.traffic_light*':
                raise ValueError('Wrong Native actor class requested')
            return self.lights

    class FakeWorld:
        def __init__(self, lights):
            self.lights = lights

        def get_actors(self):
            return FakeActors(self.lights)

    governing = FakeLight(17, [(158190, -1)])
    other = FakeLight(18, [(158194, -1)])
    if select_native_governing_head(FakeWorld([other, governing])) is not governing:
        raise AssertionError('Native selector chose a head for another lane')
    for lights, expected in (([other], 'found 0'), ([governing, governing], 'found 2')):
        try:
            select_native_governing_head(FakeWorld(lights))
        except ValueError as error:
            if expected not in str(error):
                raise
        else:
            raise AssertionError('Native selector accepted absent or ambiguous governance')
    proof['native_selector_cpu_test'] = 'unique affected ego lane; rejects zero/two matches'
    proof.update(provenance_kind='authored_cpu_site', physical_acceptance_claimed=False,
                 native_affected_lane_readback_pending=True)
    print(json.dumps(proof, sort_keys=True))


if __name__ == '__main__':
    main()
