"""CPU checks for the signed local-road Native construction request."""
from copy import deepcopy
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from nonthrough_scene import request, validate
from nonthrough_native_construction import original_map_check


def rejects(fn, fragment):
    try:
        fn()
    except ValueError as exc:
        if fragment not in str(exc):
            raise AssertionError(str(exc)) from exc
    else:
        raise AssertionError(f'Expected rejection: {fragment}')


def main():
    variants = [
        request('stop_unobligated_inside'),
        request('stop_roll_through_inside', action='roll_through'),
        request('yield_unobligated_approaching', sign='yield', counterpart_start_y=-100,
                action='yield_then_proceed'),
        request('yield_no_yield_approaching', sign='yield', counterpart_start_y=-100,
                action='no_yield'),
        request('stop_crosswalk_reference', reference='crosswalk'),
        request('stop_nearest_viewpoint', reference='nearest_viewpoint'),
        request('counterpart_signed', counterpart_control='stop'),
        request('police_control', exception='police'),
        request('signal_control', exception='signal'),
    ]
    class Map:
        def __init__(self, xodr): self.xodr = xodr
        def to_opendrive(self): return self.xodr
    class World:
        def __init__(self, xodr): self.map = Map(xodr)
        def get_map(self): return self.map
    plan = json.loads((Path(__file__).resolve().parent / 'case-plan.json').read_text())
    for case in plan['cases']:
        slug = case['case_id'].removeprefix(plan['assignment_id'] + '__')
        variants.append(request(slug, **case['construction_request']))
    assert len(plan['cases']) == 10 and len(plan['comparisons']) == 7
    for variant in variants:
        result = validate(variant)
        assert original_map_check(World(variant['road_opendrive']), variant) == variant['road_opendrive']
        assert result['entrances_inventoried'] == 4 and result['planned_frames'] == 600
        assert not result['original_road_kind_verified'] and not result['original_controls_verified']
    changed = deepcopy(variants[0]); del changed['entrance_control_inventory_requested']['east_opposing']
    rejects(lambda: validate(changed), 'Whole-intersection entrance inventory')
    changed = deepcopy(variants[0]); changed['road_kind_native_verified'] = True
    rejects(lambda: validate(changed), 'Road-kind source claim')
    changed = deepcopy(variants[0]); changed['counterpart_control'] = 'stop'
    rejects(lambda: validate(changed), 'Entrance obligation mismatch')
    changed = deepcopy(variants[0]); root = ET.fromstring(changed['road_opendrive'])
    other = root.find("road[@id='111326']/signals")
    ET.SubElement(other, 'signal', id='stop-111326', name='STOP')
    changed['road_opendrive'] = ET.tostring(root, encoding='unicode')
    rejects(lambda: validate(changed), 'Counterpart approach unexpectedly signed')
    changed = deepcopy(variants[0]); changed['cameras'] = changed['cameras'][:3]
    rejects(lambda: validate(changed), 'Exact four-camera plan')
    changed = deepcopy(variants[0]); changed['planned_frames'] = 300
    rejects(lambda: validate(changed), 'Exact thirty-second plan')
    changed = deepcopy(variants[-1]); changed['exception_source_required'] = None
    rejects(lambda: validate(changed), 'Exception source missing')
    changed = deepcopy(variants[0]); root = ET.fromstring(changed['road_opendrive'])
    root.find("road[@id='111325']/signals").clear()
    rejects(lambda: original_map_check(World(ET.tostring(root, encoding='unicode')), changed),
            'governing subject sign')
    print('ten exact planned and nine diagnostic local-road requests and original map readbacks pass; eight unsupported or missing-source mutations reject')


if __name__ == '__main__':
    main()
