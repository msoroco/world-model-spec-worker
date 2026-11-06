"""Create two unselected, synthetic original-sample diagnostics for C10014."""
import json
from pathlib import Path

from native.geometry import (ACCESS_BOUNDS_M,ALLEY_LANE_ID,ALLEY_ROAD_ID,
                             ENTRANCE_BOUNDS_M,STOP_X_M,STOP_Y_M,check)
from native.measure_entrance import measure

HERE=Path(__file__).resolve().parent
OUTPUT=HERE/'draft-measurements'


def write_rows(path,rows):
    path.write_text(''.join(json.dumps(row,allow_nan=False)+'\n' for row in rows))


def build():
    check();OUTPUT.mkdir(exist_ok=True)
    receipts=[]
    for suffix,stop_x in STOP_X_M.items():
        folder=OUTPUT/suffix;folder.mkdir(exist_ok=True)
        geometry={'alley_native_road_id':ALLEY_ROAD_ID,
                  'alley_native_lane_id':ALLEY_LANE_ID,
                  'driveway_entrance_native_xy_bounds_m':ENTRANCE_BOUNDS_M,
                  'abutting_property_access_native_xy_bounds_m':ACCESS_BOUNDS_M,
                  'native_alley_and_access_design_verified':False,
                  'scope':'authored synthetic geometry, not physical Native readback'}
        (folder/'road_geometry.json').write_text(json.dumps(geometry,indent=2)+'\n')
        samples=[]
        for index in range(480):
            x=min(-45+.25*index,stop_x)
            previous=min(-45+.25*(index-1),stop_x) if index else x
            body=[[x-2.6,STOP_Y_M-1.1],[x-2.6,STOP_Y_M+1.1],
                  [x+2.6,STOP_Y_M+1.1],[x+2.6,STOP_Y_M-1.1]]
            samples.append({'native_frame':100+index,'time_s':(index+1)/20,
                            'native_center_xy_m':[x,STOP_Y_M],
                            'native_forward_xy':[1,0],
                            'native_body_xy_m':body,
                            'native_road_id':ALLEY_ROAD_ID,'native_lane_id':ALLEY_LANE_ID,
                            'speed_mps':(x-previous)*20,
                            'synthetic_diagnostic':True})
        source=folder/'native_samples.jsonl';write_rows(source,samples)
        receipt=measure(source,folder/'road_geometry.json')
        expected=0.0 if suffix=='reference' else 5.2
        if abs(receipt['max_entrance_overlap_m']-expected)>1e-6:
            raise ValueError('Unexpected entrance overlap')
        if receipt['native_design_verified'] or receipt['legal_blocking_verdict_claimed']:
            raise ValueError('Synthetic fixture claimed physical or legal result')
        (folder/'measurement.json').write_text(json.dumps(receipt,indent=2)+'\n')
        missing=folder/'missing-native-samples.jsonl'
        try:measure(missing,folder/'road_geometry.json')
        except ValueError as exc:
            if str(exc)!='Missing required source: missing-native-samples.jsonl':raise
        else:raise ValueError('Missing source was accepted')
        bad=[{**row,'native_lane_id':-2} for row in samples]
        bad_path=folder/'wrong-lane.jsonl';write_rows(bad_path,bad)
        try:measure(bad_path,folder/'road_geometry.json')
        except ValueError as exc:
            if str(exc)!='No observed stationary alley interval':raise
        else:raise ValueError('Wrong alley lane was accepted')
        receipts.append({'suffix':suffix,'max_entrance_overlap_m':expected,
                         'stop_duration_s':receipt['stop_duration_s'],
                         'source_sha256':receipt['source_sha256'],
                         'missing_source_rejected':True,'wrong_lane_rejected':True,
                         'scope':'synthetic measurement diagnostic; no physical or legal outcome'})
    summary={'format':'c10014-draft-measurement-pair-v1','rows':receipts,
             'selected':False,'ready':False}
    (OUTPUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    return summary


if __name__=='__main__':print(json.dumps(build(),indent=2))
