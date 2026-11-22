"""Independent source-bound clear/occupied comparison for C111125."""
import argparse
import json
from pathlib import Path

FIXED=('law_id','cell_id','actor_id','map_sha256','route_sha256',
       'intersection_geometry_sha256','camera_contract_sha256','duration_s')


def audit(clear,occupied):
    for key in FIXED:
        if not clear.get(key) or not occupied.get(key):
            raise ValueError('missing fixed condition: '+key)
        if clear[key]!=occupied[key]:
            raise ValueError('fixed condition differs: '+key)
    if clear.get('case_id','').rsplit('__',1)[-1]!='clear_straight' or occupied.get('case_id','').rsplit('__',1)[-1]!='yield_straight':
        raise ValueError('comparison case identity differs')
    for record in (clear,occupied):
        measured=record.get('measurement',{})
        if measured.get('format')!='worker-straight-arrow-measurements' or not all(
                measured.get('sources',{}).get(name) for name in (
                    'signal-head-history.jsonl','ego-body-history.jsonl',
                    'participant-history.jsonl','intersection-context.json')):
            raise ValueError('missing source-bound straight-arrow measurement')
        if measured.get('first_sole_arrow_frame') is None or measured.get('first_ego_intersection_entry_frame') is None:
            raise ValueError('arrow exhibition or straight entry not observed')
        if measured.get('entry_without_verified_arrow_frames'):
            raise ValueError('entry lacks verified sole-arrow source')
        if abs(measured.get('observed_heading_change_deg',999))>15:
            raise ValueError('observed maneuver differs from straight route')
    if clear['measurement']['lawfully_occupied_frames']:
        raise ValueError('clear case contains lawful occupancy')
    if not occupied['measurement']['lawfully_occupied_frames']:
        raise ValueError('occupied case lacks lawful occupancy')
    if occupied['measurement']['ego_past_stop_line_during_occupancy_frames']:
        raise ValueError('occupied case crossed stop line before yield cleared')
    return {'comparison_id':'straight_arrow_yield_occupancy','passed':True,
            'fixed_conditions':list(FIXED),
            'difference':'original lawful participant occupancy at sole-arrow exhibition',
            'legal_verdict':None}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('clear');parser.add_argument('occupied')
    args=parser.parse_args()
    print(json.dumps(audit(json.loads(Path(args.clear).read_text()),
                           json.loads(Path(args.occupied).read_text())),indent=2))


if __name__=='__main__':main()
