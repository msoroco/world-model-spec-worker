"""Independent raw-frame audit of the six source-hashed rider timing fixtures."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
RIDERS=('bicycle','electric_bicycle','electric_scooter')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def crosses(body, box):
    xs=[p[0] for p in body]
    ys=[p[1] for p in body]
    return min(xs)<box[2] and max(xs)>box[0] and min(ys)<box[3] and max(ys)>box[1]


def main():
    summary=read(HERE/'rider-timing-prototype.json')
    assert summary['passed'] and summary['selected'] is summary['accepted'] is False
    assert len(summary['receipts'])==6 and summary['changed_source_negatives']==6
    pairs={}
    for item in summary['receipts']:
        rider_type,response=item['case'].rsplit('-',1)
        assert rider_type in RIDERS and response in ('clear','conflict')
        sources={name:ROOT/path for name,path in item['sources'].items()}
        assert all(path.is_file() for path in sources.values())
        manifest=read(sources['manifest'])
        geometry=read(sources['geometry'])
        assert manifest['source_kind']=='synthetic_native_shaped_diagnostic'
        assert manifest['rider_type']==rider_type
        assert manifest['samples_sha256']==sha(sources['samples'])
        assert manifest['geometry_sha256']==sha(sources['geometry'])==summary['geometry_sha256']
        box=geometry['conflict_native_xy_bounds_m']
        rows=[json.loads(line) for line in sources['samples'].read_text().splitlines()]
        assert len(rows)==480
        assert [r['native_frame'] for r in rows]==list(range(1000,1480))
        assert all(abs(r['time_s']-i*.05)<1e-8 for i,r in enumerate(rows))
        assert all(r['rider_actor_id']=='rider-1' and r['rider_type']==rider_type and
                   r['rider_native_road_id']==1 and r['rider_native_lane_id']==-2 and
                   r['ego_native_road_id']==2 for r in rows)
        rider=[i for i,row in enumerate(rows) if crosses(row['rider_body_xy'],box)]
        ego=[i for i,row in enumerate(rows) if crosses(row['ego_body_xy'],box)]
        assert rider and ego
        measured=item['measurement']
        assert measured['first_rider_frame']==rows[rider[0]]['native_frame']
        assert measured['last_rider_frame']==rows[rider[-1]]['native_frame']
        assert measured['first_ego_frame']==rows[ego[0]]['native_frame']
        assert measured['simultaneous_conflict_frames']==len(set(rider)&set(ego))
        assert measured['ego_entered_after_rider_cleared']==(ego[0]>rider[-1])
        assert measured['source_sha256']=={'samples':sha(sources['samples']),
                                           'geometry':sha(sources['geometry']),
                                           'manifest':sha(sources['manifest'])}
        pairs.setdefault(rider_type,{})[response]={'first_ego':ego[0],
                                                     'last_rider':rider[-1],
                                                     'simultaneous':len(set(rider)&set(ego)),
                                                     'rider_trace':[(r['rider_body_xy'],r['rider_speed_mps']) for r in rows],
                                                     'ego_trace':[(r['ego_body_xy'],r['ego_speed_mps']) for r in rows]}
    for rider_type,pair in pairs.items():
        clear,conflict=pair['clear'],pair['conflict']
        assert clear['rider_trace']==conflict['rider_trace']
        assert clear['last_rider']==conflict['last_rider']==217
        assert clear['first_ego']==262 and conflict['first_ego']==187
        assert clear['simultaneous']==0 and conflict['simultaneous']==31
    assert len({json.dumps(pairs[t]['clear']['ego_trace']) for t in RIDERS})==1
    assert len({json.dumps(pairs[t]['conflict']['ego_trace']) for t in RIDERS})==1
    return {'passed':True,'rider_identities':list(RIDERS),
            'controlled_pairs':len(pairs),'source_summary_sha256':sha(HERE/'rider-timing-prototype.json'),
            'legal_yield_observed':False,'selected':False,'accepted':False}


if __name__=='__main__':
    print(json.dumps(main(),indent=2))
