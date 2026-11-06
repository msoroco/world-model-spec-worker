"""Independent raw-source controlled comparison of one versus two lanes."""
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
sys.path.insert(0,str(HERE/'native'))
from measure_gap import measure as measure_single
from two_lane_exception import measure as measure_two

spec=importlib.util.spec_from_file_location('fixture',HERE/'prove-two-lane-saved-processing.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
single=ROOT/'.runtime-work/c102372-saved-processing/probe_2-positive'
with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work',prefix='c102372-two-lane-comparison-') as temporary:
    double=fixture.make_source(Path(temporary)/'double')
    a=[json.loads(line) for line in (single/'native_samples.jsonl').read_text().splitlines()]
    b=[json.loads(line) for line in (double/'native_samples.jsonl').read_text().splitlines()]
    if len(a)!=480 or len(b)!=480 or a!=b:
        raise AssertionError('Controlled truck traces changed with lane count')
    first=measure_single(single);second=measure_two(double)
    if first['relation_to_500ft']!='below' or second['relation_to_500ft']!='below' or \
            abs(first['min_surface_gap_m']-second['min_surface_gap_m'])>.002:
        raise AssertionError('Controlled truck surface gap differs')
    road_a=ET.parse(single/'road.xodr').getroot().find('road')
    road_b=ET.parse(double/'road.xodr').getroot().find('road')
    for name in ('planView','elevationProfile'):
        if ET.tostring(road_a.find(name))!=ET.tostring(road_b.find(name)):
            raise AssertionError('Controlled hill-crest geometry changed')
    lanes_a=road_a.findall('lanes/laneSection/right/lane')
    lanes_b=road_b.findall('lanes/laneSection/right/lane')
    if [item.get('id') for item in lanes_a]!=['-1'] or \
            [item.get('id') for item in lanes_b]!=['-1','-2']:
        raise AssertionError('Two-lane comparison treatment differs')
    print(json.dumps({'passed':True,'frames':480,'truck_traces_identical':True,
        'single_direction_lanes':1,'double_direction_lanes':2,
        'minimum_surface_gap_m':first['min_surface_gap_m'],
        'physical_or_legal_verdict_claim':False},sort_keys=True))
