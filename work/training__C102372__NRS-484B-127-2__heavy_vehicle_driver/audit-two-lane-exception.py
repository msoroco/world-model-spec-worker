"""Independently read the two-lane diagnostic sources and recompute its key facts."""
import importlib.util
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'native'))
from two_lane_exception import measure,two_lane_open_drive
from measure_gap import sha

spec=importlib.util.spec_from_file_location('fixture',HERE/'prove-synthetic-gap.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)

root=fixture.write_case('probe_2')
(root/'road.xodr').write_text(two_lane_open_drive()+'\n')
context=json.loads((root/'following_context.json').read_text())
context['same_direction_lane_count']=2
(root/'following_context.json').write_text(json.dumps(context,sort_keys=True)+'\n')
names=('native_samples.jsonl','following_context.json','road.xodr')
(root/'source-manifest.json').write_text(json.dumps({'format':'c102372-truck-follow-source-v1',
    'sha256':{name:sha(root/name) for name in names}},sort_keys=True)+'\n')

measurement=measure(root)
road=ET.parse(root/'road.xodr').getroot().find('road')
right=road.findall('lanes/laneSection/right/lane')
if [(int(l.get('id')),float(l.find('width').get('a'))) for l in right]!=[(-1,4.0),(-2,4.0)]:
    raise AssertionError('Independent road lane readback differs')
rows=[json.loads(line) for line in (root/'native_samples.jsonl').read_text().splitlines()]
if len(rows)!=480 or [row['native_frame'] for row in rows]!=list(range(480)):
    raise AssertionError('Independent frame continuity differs')
gaps=[]
for row in rows:
    ego=row['ego'];lead=row['lead']
    if any(actor['lane_id']!=-1 or actor['road_id']!=1 for actor in (ego,lead)):
        raise AssertionError('Independent actor lane differs')
    for actor in (ego,lead):
        ys=[point[1] for point in actor['body_xy_m']]
        if min(ys)<=-4 or max(ys)>=0 or max(ys)-min(ys)<80*.0254:
            raise AssertionError('Independent truck lane/width differs')
    gaps.append(min(point[0] for point in lead['body_xy_m'])-
                max(point[0] for point in ego['body_xy_m']))
if abs(min(gaps)-measurement['minimum_horizontal_body_gap_m'])>1e-4 or max(gaps)>=500*.3048:
    raise AssertionError('Independent gap measurement differs')
if measurement['physical_lane_availability_verified'] or measurement['legal_verdict_claimed']:
    raise AssertionError('Diagnostic claims physical or legal proof')
print(json.dumps({'passed':True,'frames':len(rows),'same_direction_lanes':[-1,-2],
                  'minimum_horizontal_gap_m':min(gaps),'physical_claim':False},sort_keys=True))
