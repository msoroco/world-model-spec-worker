"""Independent raw-source audit of the controlled lead-braking diagnostic."""
import importlib.util
import json
import math
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'native'))
from conditions_qualifier import measure

spec=importlib.util.spec_from_file_location('fixture',HERE/'prove-conditions-qualifier.py')
fixture=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixture)
roots={key:fixture.write_case(key=='lead_brake') for key in ('steady','lead_brake')}
values={key:measure(root) for key,root in roots.items()}
rows={key:[json.loads(line) for line in (root/'native_samples.jsonl').read_text().splitlines()]
      for key,root in roots.items()}
if any(len(sample)!=480 for sample in rows.values()):raise AssertionError('Frame count')
for index in range(161):
    steady=rows['steady'][index];brake=rows['lead_brake'][index]
    for actor in ('ego','lead'):
        if steady[actor]['body_xy_m']!=brake[actor]['body_xy_m'] or \
                steady[actor]['speed_mps']!=brake[actor]['speed_mps']:
            raise AssertionError('Pre-event truck trace differs')
def gap(row):
    return min(x for x,_ in row['lead']['body_xy_m'])-max(x for x,_ in row['ego']['body_xy_m'])
steady_gaps=[gap(row) for row in rows['steady']]
brake_gaps=[gap(row) for row in rows['lead_brake']]
profile=ET.parse(roots['lead_brake']/'road.xodr').getroot().find('road').findall('elevationProfile/elevation')
def surface_gap(row):
    x0=max(x for x,_ in row['ego']['body_xy_m'])
    x1=min(x for x,_ in row['lead']['body_xy_m'])
    count=math.ceil((x1-x0)/.1);step=(x1-x0)/count;distance=0
    for index in range(count):
        station=x0+(index+.5)*step
        segment=max((p for p in profile if float(p.get('s'))<=station),key=lambda p:float(p.get('s')))
        u=station-float(segment.get('s'))
        slope=float(segment.get('b'))+2*float(segment.get('c'))*u+3*float(segment.get('d'))*u*u
        distance+=math.hypot(1,slope)*step
    return distance
independent_surface_min=min(surface_gap(row) for row in rows['lead_brake'])
if abs(min(steady_gaps)-155)>1e-6 or abs(min(brake_gaps)-139)>1e-6 or \
        not values['steady']['minimum_surface_gap_m']>152.4 or \
        not values['lead_brake']['minimum_surface_gap_m']<152.4 or \
        not values['lead_brake']['surface_gap_compression_m']>15 or \
        abs(independent_surface_min-values['lead_brake']['minimum_surface_gap_m'])>.002:
    raise AssertionError('Independent gap values differ')
if any(row['obstacle'] is not None for row in rows['steady']) or \
        any(row['obstacle'] is None for row in rows['lead_brake']):
    raise AssertionError('Obstacle source presence differs')
if rows['lead_brake'][160]['lead']['speed_mps']!=8 or \
        rows['lead_brake'][200]['lead']['speed_mps']!=0 or \
        rows['lead_brake'][180]['ego']['speed_mps']!=8 or \
        rows['lead_brake'][260]['ego']['speed_mps']!=0:
    raise AssertionError('Independent braking timing differs')
if values['lead_brake']['physical_conditions_permit_verified'] or values['lead_brake']['legal_verdict_claimed']:
    raise AssertionError('Physical or legal verdict claimed')
print(json.dumps({'passed':True,'frames_per_case':480,'pre_event_truck_trace_fixed':True,
                  'steady_horizontal_gap_m':155,'braking_min_horizontal_gap_m':139,
                  'braking_min_surface_gap_m':round(independent_surface_min,4),
                  'physical_or_legal_verdict_claim':False},sort_keys=True))
