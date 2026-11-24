"""Build and test a controlled 600-frame opening/barrier geometry diagnostic."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0,str(HERE/'native'))
from measure_median import evaluate  # noqa: E402


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value):
    path.write_text(json.dumps(value,indent=2)+'\n')


def fixture(suffix,cross_x):
    folder=HERE/'fixtures/median'/suffix
    folder.mkdir(parents=True,exist_ok=True)
    geometry={'format':'c124163-authored-median-geometry-v1',
              'median_bounds_m':[-20,-2,20,2],
              'opening_bounds_m':[-3,-2,3,2],
              'barrier_bounds_m':[[-20,-2,-3,2],[3,-2,20,2]],
              'public_authority_establishment_verified':False}
    write(folder/'geometry.json',geometry)
    rows=[]
    for index in range(600):
        y=round(-12+.1*min(index,240),6)
        body=[[cross_x-.9,y-2.3],[cross_x+.9,y-2.3],
              [cross_x+.9,y+2.3],[cross_x-.9,y+2.3]]
        rows.append({'native_frame':1000+index,'video_frame':index,
                     'time_s':index/20,'native_body_xy_m':body,
                     'speed_mps':2.0 if index<240 else 0.0,
                     'source_scope':'synthetic crossing geometry only; not a Native turn'})
    (folder/'body.jsonl').write_text(''.join(json.dumps(row,separators=(',',':'))+'\n'
                                          for row in rows))
    manifest={'format':'c124163-median-source-manifest-v1',
              'case_suffix':suffix,'source_kind':'synthetic_cpu_geometry_diagnostic',
              'accepted':False,'sha256':{'geometry.json':sha(folder/'geometry.json'),
                                         'body.jsonl':sha(folder/'body.jsonl')}}
    write(folder/'sources.json',manifest)
    return folder


def rejection(folder,change,error):
    with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work',
                                     prefix='c124163-median-negative-') as temp:
        negative=Path(temp)/'fixture'
        shutil.copytree(folder,negative)
        change(negative)
        try:
            evaluate(negative)
        except ValueError as exc:
            if error not in str(exc):
                raise AssertionError(str(exc))
            return str(exc)
        raise AssertionError('Invalid source was accepted')


def main():
    folders={'probe_a':fixture('probe_a',0.0),'probe_b':fixture('probe_b',12.0)}
    observed={suffix:evaluate(folder) for suffix,folder in folders.items()}
    assert observed['probe_a']['barrier_occupied_frames']==0
    assert observed['probe_a']['opening_occupied_frames']>0
    assert observed['probe_b']['opening_occupied_frames']==0
    assert observed['probe_b']['barrier_occupied_frames']>0
    assert observed['probe_a']['median_occupied_frames']==observed['probe_b']['median_occupied_frames']

    def corrupt_bytes(folder):
        with (folder/'body.jsonl').open('a') as stream:stream.write('{}\n')
    def relabel(folder):
        data=json.loads((folder/'sources.json').read_text())
        data['source_kind']='original_native'
        write(folder/'sources.json',data)
    def gap(folder):
        path=folder/'body.jsonl'
        rows=[json.loads(line) for line in path.read_text().splitlines()]
        rows[80]['native_frame']+=1
        path.write_text(''.join(json.dumps(row,separators=(',',':'))+'\n' for row in rows))
        data=json.loads((folder/'sources.json').read_text())
        data['sha256']['body.jsonl']=sha(path)
        write(folder/'sources.json',data)
    negatives={suffix:{'changed_source_hash':rejection(folder,corrupt_bytes,'Source hash differs'),
                       'synthetic_relabel':rejection(folder,relabel,'cannot be relabeled'),
                       'native_frame_gap':rejection(folder,gap,'frame/time join differs')}
               for suffix,folder in folders.items()}
    proof={'format':'c124163-median-crossing-geometry-proof-v1',
           'assignment_id':HERE.name,'selected':False,'accepted':False,
           'case_sources':{suffix:{'folder':str(folder.relative_to(ROOT)),
                                    'manifest_sha256':sha(folder/'sources.json')}
                           for suffix,folder in folders.items()},
           'observed':observed,'negative_errors':negatives,
           'controlled_difference':'12 m lateral translation of otherwise identical crossing trace',
           'limitations':['synthetic crossing is not a left-turn Native route',
                          'public-authority establishment unverified',
                          'accepted originals not reviewed for equivalence']}
    target=HERE/'median-crossing-proof.json'
    write(target,proof)
    print(json.dumps({'proof_sha256':sha(target),'positive':2,'negative':6,
                      'opening_frames':observed['probe_a']['opening_occupied_frames'],
                      'barrier_frames':observed['probe_b']['barrier_occupied_frames']}))


if __name__=='__main__':main()
