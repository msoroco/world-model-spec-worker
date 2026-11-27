"""Build textual synthetic A2 packets; their facts cannot certify original conduct."""
from pathlib import Path
import hashlib
import json

from bus_location import PERMITTED, footprint_location

ROOT = Path(__file__).resolve().parent
POLYGONS = {
    'bus_stop': [[-50,-8],[-35,-8],[-35,0],[-50,0]],
    'bus_stand': [[-30,-8],[-15,-8],[-15,0],[-30,0]],
    'passenger_loading_zone': [[-10,-8],[5,-8],[5,0],[-10,0]],
    'route_origin': [[10,-8],[25,-8],[25,0],[10,0]],
    'route_destination': [[30,-8],[45,-8],[45,0],[30,0]],
}
CENTERS = {'bus_stop':[-42,-4], 'bus_stand':[-22,-4],
           'passenger_loading_zone':[-2,-4], 'route_origin':[18,-4],
           'route_destination':[38,-4], 'outside':[58,-4]}


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True)+'\n')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def footprint(center):
    x,y=center
    return [[x-3,y-1],[x+3,y-1],[x+3,y+1],[x-3,y+1]]


def build():
    plan = json.loads((ROOT/'case-plan.json').read_text())
    common = {'source_class':'synthetic_diagnostic'}
    designation_hash = hashlib.sha256(b'synthetic A2 designation only').hexdigest()
    route_hash = hashlib.sha256(b'synthetic assigned route only').hexdigest()
    for case in plan['cases']:
        suffix = case['case_id'].split('__')[-1]
        folder = ROOT/'cases'/suffix/'diagnostic-sources'
        location = case['location_kind']
        center = CENTERS[location]
        rows = []
        for i in range(900):
            if i < 200:
                x = center[0] - 12 + 12*i/200
                speed = 1.2
            elif i <= 500:
                x = center[0]
                speed = 0.0
            else:
                x = center[0] + 12*(i-500)/399
                speed = 1.2
            actual_center = [round(x,5), center[1]]
            body = footprint(actual_center)
            rows.append({'frame':i,'time_s':i/20,'bus_id':'diagnostic-bus-1',
                         'bus_center_xy_m':actual_center,
                         'bus_footprint_xy_m':body,
                         'measured_location':footprint_location(body,POLYGONS),
                         'bus_speed_mps':speed})
        values = {
          'site':{**common,'kind':'reviewed_bus_loading_site','cell_id':'C378132',
                  'layout':'business_district','public_street':True,
                  'reviewer':'synthetic diagnostic only',
                  'jurisdiction_source_sha256':hashlib.sha256(b'synthetic jurisdiction').hexdigest(),
                  'designation_source_sha256':designation_hash,
                  'boundary_source_sha256':hashlib.sha256(b'synthetic boundaries').hexdigest(),
                  'location_polygons_xy_m':POLYGONS},
          'designation':{**common,'kind':'bus_loading_designations',
                  'authority':'City Traffic Engineer','source_sha256':designation_hash,
                  'signs_reviewed':True,'designated_locations':list(PERMITTED)},
          'route':{**common,'kind':'assigned_bus_route','route_id':'synthetic-route',
                  'source_sha256':route_hash,'origin_destination_reviewed':True},
          'identity':{**common,'kind':'bus_operator_identity','bus_id':'diagnostic-bus-1',
                  'tour_bus':case['bus_class']=='tour','covered_operator':'synthetic bus driver',
                  'assigned_route':'synthetic-route',
                  'bus_class_source_sha256':hashlib.sha256(b'synthetic bus classification').hexdigest(),
                  'operator_source_sha256':hashlib.sha256(b'synthetic operator').hexdigest()},
          'activity':{**common,'kind':'bus_stop_activity_review',
                  'independent_reviewer':'synthetic diagnostic only',
                  'events':[{'event':'start','frame':200},{'event':'end','frame':500}]},
          'purpose':{**common,'kind':'loading_purpose_review','bus_id':'diagnostic-bus-1',
                  'loading_purpose':case['loading_purpose'],
                  'independent_reviewer':'synthetic diagnostic only',
                  'source_sha256':hashlib.sha256(('synthetic '+case['loading_purpose']).encode()).hexdigest()},
          'circumstances':{**common,'kind':'stop_circumstances_review',
                  'bus_id':'diagnostic-bus-1','stop_reason':case['stop_reason'],
                  'independent_reviewer':'synthetic diagnostic only',
                  'source_sha256':hashlib.sha256(('synthetic '+case['stop_reason']).encode()).hexdigest()},
          'native':{**common,'kind':'native_bus_frame_ledger',
                  'bus_id':'diagnostic-bus-1','frames':rows},
        }
        refs = {}
        for key,value in values.items():
            path=folder/(key+'.json')
            refs[key]={'path':str(path.relative_to(ROOT)), 'sha256':write(path,value)}
        write(ROOT/'cases'/suffix/'diagnostic-refs.json',refs)
    print(f"built {len(plan['cases'])} source-hashed synthetic A2 packets")


if __name__=='__main__':
    build()
