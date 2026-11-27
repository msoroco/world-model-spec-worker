"""Build explicitly synthetic stop-boundary packets for CPU compatibility only."""
from pathlib import Path
import hashlib
import json

ROOT=Path(__file__).resolve().parent
POLYGON=[[-42,-8],[-18,-8],[-18,0],[-42,0]]


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    plan=json.loads((ROOT/'case-plan.json').read_text())
    for case in plan['cases']:
        suffix=case['case_id'].split('__')[-1]
        folder=ROOT/'cases'/suffix/'diagnostic-sources'
        relation=case['location_relation']
        center=[-30,-4] if relation=='inside' else [-30,-12]
        footprint=[[center[0]-4,center[1]-1],[center[0]+4,center[1]-1],
                   [center[0]+4,center[1]+1],[center[0]-4,center[1]+1]]
        common={'source_class':'synthetic_diagnostic'}
        designation_hash=hashlib.sha256(b'synthetic C378132 official designation only').hexdigest()
        values={
          'site':{**common,'kind':'reviewed_bus_stop_site','cell_id':'C378132','layout':'one_way_road',
                  'stop_kind':'bus_stop','stop_id':'synthetic-stop-1','public_street':True,
                  'jurisdiction_source_sha256':hashlib.sha256(b'synthetic jurisdiction').hexdigest(),
                  'reviewer':'synthetic diagnostic only','designation_source_sha256':designation_hash,
                  'boundary_source_sha256':hashlib.sha256(b'synthetic stop polygon').hexdigest(),
                  'stop_polygon_xy_m':POLYGON},
          'designation':{**common,'kind':'bus_stop_designation','stop_id':'synthetic-stop-1',
                  'authority':'City Traffic Engineer','source_sha256':designation_hash,
                  'signed':True,'route_termini_reviewed':True,'other_permitted_locations_reviewed':True},
          'identity':{**common,'kind':'bus_operator_identity','bus_id':'diagnostic-bus-1',
                  'tour_bus':False,'covered_operator':'synthetic bus driver',
                  'assigned_route':'synthetic route','route_source_sha256':hashlib.sha256(b'synthetic route').hexdigest()},
          'activity':{**common,'kind':'bus_activity_review','conduct':case['conduct'],
                  'independent_reviewer':'synthetic diagnostic only',
                  'events':[{'event':'start','frame':200},{'event':'end','frame':500}]},
          'native':{**common,'kind':'native_bus_frame_ledger','bus_id':'diagnostic-bus-1',
                  'frames':[{'frame':i,'time_s':i/20,'bus_id':'diagnostic-bus-1',
                             'inside_stop_boundary':relation=='inside',
                             'outside_other_permitted_location':relation=='outside',
                             'bus_center_xy_m':center,'bus_footprint_xy_m':footprint,
                             'bus_speed_mps':0.0} for i in range(900)]}}
        refs={}
        for key,value in values.items():
            path=folder/(key+'.json')
            refs[key]={'path':str(path.relative_to(ROOT)),'sha256':write(path,value)}
        write(ROOT/'cases'/suffix/'diagnostic-refs.json',refs)
    print('four source-hashed synthetic bus-position diagnostic packets')


if __name__=='__main__':build()
