"""Independent saved-source audit for exact NRS 484B.113(3) cases."""
import argparse
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
SOURCES=('road.xodr','native-motion.jsonl','traffic-context.json','video_frames.jsonl',
         'trace.jsonl','overview.mkv','approach.mkv','reference_corner.mkv','driver_reference.mkv')

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def read(path):
    path=Path(path)
    if not path.is_file():raise ValueError('Missing source: '+path.name)
    return json.loads(path.read_text())

def audit(case,candidate,attempt,processing,diagnostic,omit_source):
    manifest=read(HERE/'execution-manifest.json')
    entry=next((x for x in manifest['cases'] if x['case_id']==case),None)
    if entry is None:raise ValueError('Unknown selected case')
    selected=entry if candidate=='primary' else next((x for x in entry['candidates'] if x['id']==candidate),None)
    if selected is None:raise ValueError('Unknown selected candidate')
    saved=read(processing)
    if (saved.get('passed') is not True or saved.get('recorded_only') is not True or
        saved.get('case_id')!=case or saved.get('candidate_id')!=candidate or
        saved.get('originals_preserved') is not True or
        saved.get('native_revision',{}).get('construction_sha256')!=sha(Path(attempt)/'construction.json') or
        read(Path(attempt)/'construction.json')!=read(HERE/selected['construction']) or
        saved.get('timestamp_joins',{}).get('frames')!=600 or
        saved.get('final_video_checks',{}).get('frames')!=600):
        raise ValueError('Selected saved processing or full video decode differs')
    stage=Path(saved['analysis_directory']).resolve()
    hashes={}
    for name in SOURCES:
        if name==omit_source:raise ValueError('Missing source: '+name)
        path=stage/name
        if not path.is_file():raise ValueError('Missing source: '+name)
        hashes[name]=sha(path)
    result=read(stage/'result.json');report=read(stage/'analysis-report.json')
    context=read(stage/'traffic-context.json')
    if (result.get('case_id')!=case or result.get('trace_reference')!='trace.jsonl' or
        len((stage/'trace.jsonl').read_text().splitlines())!=600 or
        len((stage/'video_frames.jsonl').read_text().splitlines())!=600 or
        result.get('legal_verdict_claimed') is not False):
        raise ValueError('Original Native identity, join or legal scope differs')
    branch=case.rsplit('__',1)[1].startswith('pedestrian_')
    key='pedestrian_requirement' if branch else 'moving_requirement'
    measure=report.get('measurements',{}).get(key,{})
    if (measure.get('method')!=('measure_pedestrian_requirement' if branch else 'measure_moving_requirement') or
        any(measure.get('sources',{}).get(name)!=hashes[name]
            for name in ('native-motion.jsonl','traffic-context.json','video_frames.jsonl')) or
        measure.get('value',{}).get('backing_frames',0)<=0 or
        measure.get('value',{}).get('simultaneous_frames',0)<=0):
        raise ValueError('Source-bound branch measurement differs')
    if (context.get('section_stem_recovered') is not True or
        context.get('other_highway_use_reviewed') is not True or
        context.get('pedestrian_actor_count_at_start')!=int(branch)):
        raise ValueError('Backing, highway traffic or pedestrian source context differs')
    if diagnostic:
        fixture=read(Path(attempt)/'compatibility.json')
        if (fixture.get('passed') is not True or fixture.get('case_id')!=case or
            fixture.get('candidate_id')!=candidate or
            fixture.get('construction_sha256')!=selected['construction_sha256']):
            raise ValueError('Diagnostic compatibility identity differs')
    else:
        provenance=read(Path(attempt)/'acquisition-provenance.json')
        if provenance.get('provenance_kind')!='native' or provenance.get('diagnostic_fixture') is True:
            raise ValueError('Original Native source required')
        pixels=read(stage/'pixel-review.json')
        if (pixels.get('review_status')!='independently_reviewed' or not pixels.get('reviewer') or
            pixels.get('frame_map_sha256')!=hashes['video_frames.jsonl'] or
            pixels.get('source_video_sha256')!=hashes['reference_corner.mkv'] or
            pixels.get('branch')!=('pedestrian' if branch else 'moving_traffic')):
            raise ValueError('Independent original pixel review incomplete')
        if result.get('physical_checks',{}).get('maneuver',{}).get('status')!='met':
            raise ValueError('Original physical backing completion unverified')
    return {'format':'c230259-independent-delivery-audit-v1','case_id':case,
        'candidate_id':candidate,'construction_sha256':selected['construction_sha256'],
        'saved_processing_sha256':sha(processing),'source_sha256':hashes,
        'diagnostic_only':diagnostic,'physical_or_legal_acceptance_claimed':False}

def main():
    p=argparse.ArgumentParser();p.add_argument('--case',required=True)
    p.add_argument('--candidate',default='primary');p.add_argument('--attempt',required=True)
    p.add_argument('--processing',required=True);p.add_argument('--output',required=True)
    p.add_argument('--diagnostic',action='store_true');p.add_argument('--omit-source',choices=SOURCES)
    a=p.parse_args()
    if a.omit_source and not a.diagnostic:raise ValueError('Source omission is diagnostic only')
    result=audit(a.case,a.candidate,a.attempt,a.processing,a.diagnostic,a.omit_source)
    output=Path(a.output)
    if output.exists():raise ValueError('Retain previous delivery audit result')
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({'passed':True,'case_id':a.case,'diagnostic_only':a.diagnostic}))

if __name__=='__main__':main()
