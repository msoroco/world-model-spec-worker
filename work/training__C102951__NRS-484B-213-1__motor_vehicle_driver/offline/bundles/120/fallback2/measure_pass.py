"""Measure a saved left-of-center pass and sight envelope; no legal verdict."""
import hashlib
import json
import math
from pathlib import Path

SOURCES=('native-observed.jsonl','road-readback.json')
BLUEPRINT='vehicle.tesla.model3'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def number(value):return type(value) in (int,float) and math.isfinite(value)


def body_bounds(row, actor, kind):
    if kind=='synthetic_cpu':
        x,y=row[actor+'_x_m'],row[actor+'_y_m']
        return x-2.2,x+2.2,y-.9,y+.9
    points=row.get(actor+'_body_xy_m')
    if not isinstance(points,list) or len(points)<4 or any(
            not isinstance(point,list) or len(point)!=2 or not all(number(v) for v in point)
            for point in points):
        raise ValueError('Original Native actor body vertices absent: '+actor)
    xs=[point[0] for point in points];ys=[point[1] for point in points]
    if max(xs)-min(xs)<1 or max(ys)-min(ys)<.5:
        raise ValueError('Original Native actor body dimensions invalid: '+actor)
    if not min(xs)<=row[actor+'_x_m']<=max(xs) or not min(ys)<=row[actor+'_y_m']<=max(ys):
        raise ValueError('Original Native actor center outside body: '+actor)
    return min(xs),max(xs),min(ys),max(ys)


def measure(folder,expected_hashes=None):
    folder=Path(folder)
    paths={name:folder/name for name in SOURCES}
    if any(not path.is_file() for path in paths.values()):raise ValueError('Required saved pass source absent')
    hashes={name:sha(path) for name,path in paths.items()}
    if expected_hashes is not None and hashes!=expected_hashes:raise ValueError('Saved pass source hash differs')
    road=json.loads(paths['road-readback.json'].read_text())
    if (road.get('format')!='c102951-road-readback-v1' or road.get('lane_count')!=2 or
            road.get('travel_directions')!=2 or road.get('centerline_y_m')!=0 or
            road.get('highway_status_reviewed') is not False or
            road.get('source_kind') not in ('synthetic_cpu','original_native')):
        raise ValueError('Two-lane two-way road readback differs')
    rows=[json.loads(line) for line in paths['native-observed.jsonl'].read_text().splitlines() if line.strip()]
    if len(rows)!=480:raise ValueError('Pass frame count differs')
    kind=road['source_kind'];entry=[];full_left=[];abreast=[];return_frames=[];gap=[];clear=[];visible=[]
    first_native=rows[0].get('native_frame');first_time=rows[0].get('time_s')
    if type(first_native) is not int or not number(first_time):raise ValueError('First Native frame/time invalid')
    passed=False
    for i,row in enumerate(rows):
        if row.get('frame')!=i or row.get('native_frame')!=first_native+i or row.get('source_kind')!=kind or row.get('ego_blueprint')!=BLUEPRINT or not number(row.get('time_s')) or abs(row['time_s']-first_time-i/20)>1e-4:
            raise ValueError('Saved pass frame or actor identity differs')
        for key in ('ego_x_m','ego_y_m','ego_speed_mps','overtaken_x_m','overtaken_y_m',
                    'overtaken_speed_mps','oncoming_x_m','oncoming_y_m','oncoming_speed_mps',
                    'driver_eye_clear_m'):
            if not number(row.get(key)):raise ValueError('Saved pass numeric observation absent: '+key)
        if row.get('sightline_visible') not in (True,False) or type(row['sightline_visible']) is not bool:
            raise ValueError('Saved sightline flag invalid')
        if (row['ego_speed_mps']<0 or row['overtaken_speed_mps']<0 or row['oncoming_speed_mps']<0 or
                row['driver_eye_clear_m']<0 or row['overtaken_y_m']>=0 or row['oncoming_y_m']<=0):
            raise ValueError('Saved traffic direction or sightline invalid')
        ego=body_bounds(row,'ego',kind)
        overtaken=body_bounds(row,'overtaken',kind)
        oncoming=body_bounds(row,'oncoming',kind)
        if ego[3]>0:
            entry.append(i);clear.append(row['driver_eye_clear_m']);visible.append(row['sightline_visible'])
            if ego[2]>0:full_left.append(i)
        if entry and ego[1]>=overtaken[0] and ego[0]<=overtaken[1]:
            abreast.append(i)
        if entry and ego[0]>overtaken[1]:
            passed=True
        if passed and ego[3]<=0:
            return_frames.append(i)
        if entry and not return_frames:
            gap.append((i,oncoming[0]-ego[1]))
    if not entry or not abreast or not return_frames or not full_left:
        raise ValueError('Saved pass entry, abreast or return absent')
    start=entry[0];finish=return_frames[0]
    if start>=abreast[0] or abreast[-1]>=finish or finish>=480:
        raise ValueError('Saved pass event order differs')
    entry_row=rows[start]
    entry_ego=body_bounds(entry_row,'ego',kind)
    entry_oncoming=body_bounds(entry_row,'oncoming',kind)
    return {'format':'c102951-saved-pass-measurement-v1','source_kind':kind,'frames':480,
            'first_left_of_center_frame':start,'first_full_left_frame':full_left[0],
            'first_abreast_frame':abreast[0],'first_return_after_pass_frame':finish,
            'left_of_center_frames':len(entry),
            'entry_oncoming_body_gap_m':round(entry_oncoming[0]-entry_ego[1],3),
            'minimum_pre_return_oncoming_body_gap_m':round(min(value for _,value in gap),3),
            'first_nonpositive_pre_return_oncoming_gap_frame':next((i for i,value in gap if round(value,3)<=0),None),
            'minimum_left_phase_driver_eye_clear_m':round(min(clear),3),
            'all_left_phase_sightline_flags_visible':all(visible),
            'highway_status_reviewed':False,'safe_distance_judgment':None,
            'interference_judgment':None,'legal_verdict':None,
            'source_hashes':hashes}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('folder');a=p.parse_args()
    print(json.dumps(measure(a.folder),indent=2))
