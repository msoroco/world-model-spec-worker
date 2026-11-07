"""Check five full-duration synthetic saved routes against Native trigger baseline."""
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE/'native'))
from fallback_triggers import evaluate_native

CASES=('witness_1','witness_2','numeric_1_0','numeric_1_1','numeric_1_2')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest=json.loads((HERE/'draft-execution-manifest.json').read_text())
    outcomes=[]
    for case in CASES:
        log=HERE/f'package-compatibility-{case}.log'
        lines=log.read_text().splitlines()
        if len(lines)!=2 or not lines[0].startswith('scratch '):
            raise ValueError('Primary package receipt incomplete')
        scratch=Path(lines[0][8:])
        package=json.loads(lines[1])
        source=scratch/'fixture/native_samples.jsonl'
        entry=next(row for row in manifest['cases'] if row['case_id'].endswith('__'+case))
        if (package['positive']['construction_sha256']!=entry['construction_sha256'] or
            package['positive']['passed'] is not True or
            not source.is_file()):
            raise ValueError('Saved fixture is not bound to current exact primary')
        rows=[json.loads(line) for line in source.read_text().splitlines()]
        if len(rows)!=480 or any(row['native_frame']!=100+i or abs(row['time_s']-(i+1)/20)>1e-8
                                 for i,row in enumerate(rows)):
            raise ValueError('Saved full-duration Native-shaped row sequence differs')
        entry_time=next((row['time_s'] for row in rows if row['native_road_id']==1 and
                         row['native_lane_id']==-1 and
                         all(-1.75<=y<=1.75 for _,y in row['native_body_xy_m'])),None)
        measured=evaluate_native(source,case)
        if (entry_time is None or entry_time>6 or
            measured['fallback1']['triggered'] or measured['fallback2']['triggered'] or
            measured['fallback1']['entered_center_lane_by_6s'] is not True):
            raise ValueError('Primary route baseline incorrectly selects fallback')
        outcomes.append({'case':case,'source_sha256':sha(source),'entry_time_s':entry_time,
                         'max_route_error_m':measured['fallback2']['max_route_error_m'],
                         'fallback1':False,'fallback2':False})
    print(json.dumps({'passed':True,'source_kind':'synthetic_local_diagnostic',
                      'full_duration_cases':5,'frames_per_case':480,'rows':outcomes,
                      'original_native_or_pixels_observed':False,'selected':False},sort_keys=True))


if __name__=='__main__':main()
