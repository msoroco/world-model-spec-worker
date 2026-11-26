"""Independent saved-source delivery audit for C245490 speed cases."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCES = ('speed-lane-history.jsonl','video_frames.jsonl','trace.jsonl',
           'capture/evidence.jsonl','road-context.json','overview.mkv','approach.mkv',
           'reference_corner.mkv','driver_reference.mkv')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    if not path.is_file():
        raise ValueError('Missing original delivery source: '+path.name)
    return json.loads(path.read_text())


def audit(case,candidate,processing,diagnostic=False,omit_source=None):
    manifest_path=ROOT/'execution-manifest.json'
    if not manifest_path.is_file():manifest_path=ROOT/'selected-draft-execution-manifest.json'
    manifest=read(manifest_path)
    entry=next((row for row in manifest['cases'] if row['case_id']==case),None)
    if entry is None:raise ValueError('Unknown exact delivery case')
    selected=entry if candidate=='primary' else next((row for row in entry['candidates'] if row['id']==candidate),None)
    if selected is None:raise ValueError('Unknown exact delivery candidate')
    saved=read(Path(processing))
    if (saved.get('passed') is not True or saved.get('recorded_only') is not True or
            saved.get('originals_preserved') is not True or saved.get('case_id')!=case or
            saved.get('candidate_id')!=candidate or
            saved.get('native_revision',{}).get('construction_sha256')!=selected['construction_sha256'] or
            saved.get('timestamp_joins',{}).get('frames')!=600 or
            saved.get('final_video_checks',{}).get('frames')!=600):
        raise ValueError('Saved processing or full frame decode differs')
    stage=Path(saved['analysis_directory'])
    hashes={}
    for name in SOURCES:
        if name==omit_source:raise ValueError('Missing original delivery source: '+name)
        path=stage/name
        if not path.is_file():raise ValueError('Missing original delivery source: '+name)
        hashes[name]=sha(path)
    result=read(stage/'result.json');analysis=read(stage/'analysis-report.json')
    context=read(stage/'road-context.json')
    if (result.get('case_id')!=case or context.get('case_id')!=case or
            len((stage/'trace.jsonl').read_text().splitlines())!=600 or
            len((stage/'video_frames.jsonl').read_text().splitlines())!=600 or
            len((stage/'capture/evidence.jsonl').read_text().splitlines())!=600):
        raise ValueError('Original actor, trace, evidence or frame source differs')
    measured=analysis.get('measurements',{}).get('speed_observation',{})
    if (measured.get('method')!='measure_speed_lane' or
            any(measured.get('sources',{}).get(name)!=hashes[name] for name in
                ('speed-lane-history.jsonl','video_frames.jsonl','trace.jsonl',
                 'capture/evidence.jsonl','road-context.json'))):
        raise ValueError('Original speed measurement source hash differs')
    if diagnostic:
        if context.get('review_kind')!='synthetic_diagnostic':
            raise ValueError('CPU diagnostic provenance differs')
    else:
        provenance=read(stage/'acquisition-provenance.json')
        if (provenance.get('provenance_kind')!='native' or
                provenance.get('diagnostic_fixture') is True or
                context.get('review_kind')!='original_source_review'):
            raise ValueError('Original Native provenance incomplete')
        pixels=read(stage/'pixel-review.json')
        if (pixels.get('review_status')!='independently_reviewed' or
                pixels.get('all_required_subject_pixels_visible') is not True or
                pixels.get('video_frame_map_sha256')!=hashes['video_frames.jsonl']):
            raise ValueError('Original source pixels lack independent review')
        if result.get('physical_checks',{}).get('maneuver',{}).get('status')!='met':
            raise ValueError('Original lane-change completion unverified')
    return {'format':'worker-lane-change-speed-delivery-audit','case_id':case,
            'candidate_id':candidate,'processing_sha256':sha(Path(processing)),
            'source_sha256':hashes,'diagnostic_only':diagnostic,
            'physical_or_legal_acceptance_claimed':False}


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--case',required=True)
    parser.add_argument('--candidate',default='primary')
    parser.add_argument('--processing',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--diagnostic',action='store_true')
    parser.add_argument('--omit-source',choices=SOURCES)
    args=parser.parse_args()
    if args.omit_source and not args.diagnostic:raise ValueError('Diagnostic omission only')
    args.output.write_text(json.dumps(audit(args.case,args.candidate,args.processing,
                                           args.diagnostic,args.omit_source),indent=2)+'\n')
