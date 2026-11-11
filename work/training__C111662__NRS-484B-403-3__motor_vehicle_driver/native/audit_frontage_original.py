"""Independent Native frontage readback audit; no district or legal verdict."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from frontage import ASSET_TERMS, MIN_FRONTAGE_M, SEGMENTS, authored_plan, clipped_frontage


def sha(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(path):
    path = Path(path)
    if not path.is_file(): raise ValueError('Missing original frontage source: '+path.name)
    return path


def inspect(plan, readback):
    if plan != authored_plan(): raise ValueError('Authored frontage plan changed')
    if readback.get('format') != 'c111662-native-frontage-readback-v1' or readback.get('source_kind') != 'original_native_geometry':
        raise ValueError('Native frontage readback format/provenance differs')
    if (readback.get('district_designation_verified') is not False or
            readback.get('building_use_legally_verified') is not False or
            readback.get('legal_verdict') is not None):
        raise ValueError('Frontage readback makes unsupported legal claim')
    bp = readback.get('blueprint_id','').lower()
    if not bp.startswith('static.prop.') or not any(term in bp for term in ASSET_TERMS):
        raise ValueError('Frontage prop lacks building-use asset identity')
    ids, intervals = readback.get('actor_ids'), readback.get('native_actor_intervals_x_m')
    stations = plan['station_x_m']
    if (not isinstance(ids,list) or len(ids)!=len(stations) or len(set(ids))!=len(ids)
            or any(type(v) is not int for v in ids) or not isinstance(intervals,list)
            or len(intervals)!=len(stations)):
        raise ValueError('Native frontage actor inventory incomplete')
    for station, interval in zip(stations, intervals):
        if (not isinstance(interval,list) or len(interval)!=2 or
                any(type(v) not in (float,int) or not math.isfinite(v) for v in interval) or
                not interval[0] <= station <= interval[1]):
            raise ValueError('Native frontage bounding interval misses station')
    measured = sum(clipped_frontage(intervals,segment) for segment in SEGMENTS)
    if measured+1e-9 < MIN_FRONTAGE_M:
        raise ValueError('Native frontage below 300 feet')
    if abs(measured-readback.get('native_frontage_m',-1))>1e-6:
        raise ValueError('Native frontage length differs from bounding vertices')
    return {'native_frontage_m':measured,'native_frontage_ft':measured*3.280839895013123,
            'actor_count':len(ids),'blueprint_id':readback['blueprint_id'],
            'district_designation_verified':False,'legal_verdict':None}


def audit(bundle, attempt):
    bundle, attempt = Path(bundle), Path(attempt)
    plan_path = require(bundle/'frontage-plan.json')
    readback_path = require(attempt/'native-frontage-readback.json')
    map_path = require(attempt/'native-map-readback.json')
    capture_path = require(attempt/'native-capture-report.json')
    plan,readback,mapping,capture = (json.loads(p.read_text()) for p in
                                    (plan_path,readback_path,map_path,capture_path))
    measured = inspect(plan,readback)
    road = 'divided-highway.xodr' if bundle.name.startswith('divided_') else 'district-crossroads.xodr'
    if mapping.get('source_kind')!='original_native' or mapping.get('road_sha256')!=sha(require(bundle/road)):
        raise ValueError('Native map/road frontage source differs')
    if mapping.get('ego_actor_id') in readback['actor_ids']:
        raise ValueError('Frontage prop reused ego actor identity')
    if capture.get('error') is not None or capture.get('observed_frames')!=800:
        raise ValueError('Original Native capture incomplete')
    result={'format':'c111662-original-frontage-audit-v1','passed':True,
            'case_id':capture['case_id'],'candidate_id':capture['candidate_id'],
            'sources':{'frontage-plan.json':sha(plan_path),
                       'native-frontage-readback.json':sha(readback_path),
                       'native-map-readback.json':sha(map_path),
                       'native-capture-report.json':sha(capture_path),road:sha(bundle/road)},
            'measurement':measured,'building_use_review_pending':True,
            'district_designation_verified':False,'legal_verdict':None}
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--bundle',required=True)
    p.add_argument('--attempt',required=True)
    p.add_argument('--output',required=True)
    a=p.parse_args()
    Path(a.output).write_text(json.dumps(audit(a.bundle,a.attempt),indent=2)+'\n')
