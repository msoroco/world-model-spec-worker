"""Independent source and threshold audit for six rider cases and four variants."""
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
BOX=(-2.5,-5.0,2.5,-3.0)
FIXTURES={'baseline':(False,False,False),'short_runway':(True,False,False),
          'late_entry':(False,True,False),'occluded':(False,False,True)}


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def read(path):return json.loads(path.read_text())
def intersects(body):
    xs=[p[0] for p in body];ys=[p[1] for p in body]
    return min(xs)<BOX[2] and max(xs)>BOX[0] and min(ys)<BOX[3] and max(ys)>BOX[1]


def main():
    proof=read(HERE/'rider-fallback-trigger-proof.json')
    assert proof['passed'] and len(proof['rows'])==24
    assert proof['selected'] is proof['accepted'] is False
    assert proof['prototype_sha256']==sha(HERE/'rider-timing-prototype.json')
    seen=set();crossings=0
    for item in proof['rows']:
        case=item['case'];fixture=item['fixture']
        assert (case,fixture) not in seen and fixture in FIXTURES
        seen.add((case,fixture))
        folder=ROOT/'.runtime-work/c10052-rider-trigger-sources'/(case+'-'+fixture)
        manifest_path=folder/'rider-trigger-sources.json'
        manifest=read(manifest_path)
        assert item['source_manifest_sha256']==sha(manifest_path)
        assert manifest['case_id']==case and manifest['fixture']==fixture
        assert manifest['source_kind']=='synthetic_cpu_fixture' and manifest['accepted'] is False
        for name,digest in manifest['sha256'].items():assert sha(folder/name)==digest
        samples=[json.loads(line) for line in (folder/'native_rider_ego_samples.jsonl').read_text().splitlines()]
        visibility=[json.loads(line) for line in (folder/'camera_visibility.jsonl').read_text().splitlines()]
        assert len(samples)==len(visibility)==480
        assert all(a['native_frame']==b['native_frame']==1000+i and
                   a['time_s']==b['time_s']==round(i*.05,6)
                   for i,(a,b) in enumerate(zip(samples,visibility)))
        rider=[i for i,row in enumerate(samples) if intersects(row['rider_body_xy'])]
        ego=[i for i,row in enumerate(samples) if intersects(row['ego_body_xy'])]
        visible=sum(visibility[i]['rider_and_ego_body_visible'] is True for i in rider)
        start_x=sum(p[0] for p in samples[0]['ego_body_xy'])/4
        runway=-9-start_x;error=abs(samples[ego[0]]['native_frame']-manifest['expected_ego_frame'])
        fraction=visible/len(rider)
        triggers=(runway<35,error>5,fraction<.95)
        assert triggers==FIXTURES[fixture]
        assert item['approach_runway_m']==runway
        assert item['ego_entry_error_frames']==error
        assert abs(item['body_visible_fraction']-fraction)<1e-6
        assert item['first_ego_frame']==samples[ego[0]]['native_frame']
        assert item['last_rider_frame']==samples[rider[-1]]['native_frame']
        assert item['rider_conflict_frames']==len(rider)
        assert item['visible_conflict_frames']==visible
        crossings+=sum(triggers)
    assert len(seen)==24 and crossings==proof['isolated_crossings']==18
    assert proof['changed_visibility_negatives']==24
    return {'passed':True,'rows':24,'isolated_crossings':18,
            'source_proof_sha256':sha(HERE/'rider-fallback-trigger-proof.json'),
            'original_camera_pixels_verified':False,'selected':False,'accepted':False}


if __name__=='__main__':print(json.dumps(main(),indent=2))
