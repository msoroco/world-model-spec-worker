"""Source-only original Native comparison for both post-stop precedence duties."""
import argparse
import hashlib
import json
from pathlib import Path

from native.original_measure import measure

BASE='training__C111331__NRS-484B-250-4__motor_vehicle_driver'
NAMES=('prior_stop_yield','prior_stop_no_yield','inside_vehicle_no_yield')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def rows(path):return [json.loads(x) for x in Path(path).read_text().splitlines()]


def audit(paths):
    data={name:Path(paths[name]) for name in NAMES}
    metric={name:measure(path) for name,path in data.items()}
    config={name:json.loads((path/'config.json').read_text()) for name,path in data.items()}
    for name in NAMES:
        if config[name].get('case_id')!=BASE+'__'+name:
            raise ValueError('Original precedence case identity differs')
    reference=config[NAMES[0]]
    for name in NAMES[1:]:
        for key in ('law_id','cell_id','actor','rate_hz','frames','cameras','required_atoms','source_packets'):
            if reference.get(key)!=config[name].get(key):
                raise ValueError('Fixed precedence configuration differs: '+key)
        if sha(data[NAMES[0]]/'road.xodr')!=sha(data[name]/'road.xodr'):
            raise ValueError('Original precedence road differs')
    actors={name:rows(path/'native-raw-actors.jsonl') for name,path in data.items()}
    other_clear={}
    for name,stream in actors.items():
        other_clear[name]=next((i for i,row in enumerate(stream)
            if min(point[1] for point in row['other']['body_native_xyz_m'])>20),None)
        if other_clear[name] is None or not metric[name]['pre_line_low_speed_frames']:
            raise ValueError('Original post-stop participant history incomplete')
        if metric[name]['other_pre_line_low_speed_first_frame'] is None:
            raise ValueError('Other vehicle never completed pre-line low-speed probe')
    for index in range(600):
        other=actors[NAMES[0]][index]['other']
        for name in NAMES[1:]:
            test=actors[name][index]['other']
            if (any(abs(a-b)>0.5 for a,b in zip(other['center_native_xyz_m'],test['center_native_xyz_m'])) or
                    abs(other['speed_mps']-test['speed_mps'])>0.2):
                raise ValueError('Original fixed other-vehicle trajectory differs')
    y=metric['prior_stop_yield'];p=metric['prior_stop_no_yield'];i=metric['inside_vehicle_no_yield']
    if not (y['other_pre_line_low_speed_first_frame']<p['ego_entry_frame']<p['other_entry_frame'] and
            i['other_entry_frame']<i['ego_entry_frame']<other_clear['inside_vehicle_no_yield'] and
            other_clear['prior_stop_yield']<y['ego_entry_frame']):
        raise ValueError('Original post-stop precedence ordering differs')
    return {'format':'c111331-original-precedence-audit-v1',
            'case_ids':[BASE+'__'+name for name in NAMES],
            'measurements':metric,'other_clear_frames':other_clear,
            'fixed_other_trajectory_checked':True,
            'original_native_sources_joined':True,'actual_pixels_reviewed':False,
            'legal_verdict':None}


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in NAMES:p.add_argument('--'+name.replace('_','-'),required=True)
    p.add_argument('--output',required=True);a=p.parse_args()
    paths={name:getattr(a,name) for name in NAMES}
    Path(a.output).write_text(json.dumps(audit(paths),indent=2)+'\n')
