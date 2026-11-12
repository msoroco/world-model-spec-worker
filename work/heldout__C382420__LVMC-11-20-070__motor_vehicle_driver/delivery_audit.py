"""Independent saved-source and full-video audit for LVMC 11.20.070."""
import argparse
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'runtime'))
from scenario_pipeline.worker_exchange import media
from space_measure import analyze as measure_space

SOURCES=('space_scene.json','space_frames.jsonl','video_frames.jsonl','trace.jsonl')
CAMERAS=('overview','approach','reference_corner','driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(x) for x in Path(path).read_text().splitlines() if x.strip()]


def audit(case,analysis,decode_dir,diagnostic_fixture=False):
    root=Path(analysis)
    for name in SOURCES+('config.json','analysis-report.json','result.json'):
        if not (root/name).is_file():
            raise ValueError('Missing saved delivery source: '+name)
    config=json.loads((root/'config.json').read_text())
    report=json.loads((root/'analysis-report.json').read_text())
    result=json.loads((root/'result.json').read_text())
    if any(x!=case for x in (config.get('selected_case_id'),report.get('case_id'),result.get('case_id'))):
        raise ValueError('Exact saved delivery identity differs')
    scene=json.loads((root/SOURCES[0]).read_text())
    frames,mapping,trace=(rows(root/name) for name in SOURCES[1:])
    if not frames or not (len(frames)==len(mapping)==len(trace)):
        raise ValueError('Saved body, camera and trace frame counts differ')
    for index,(body,video,state) in enumerate(zip(frames,mapping,trace)):
        if (body.get('frame')!=index or video.get('video_frame')!=index or
                body.get('carla_frame')!=video.get('carla_frame') or
                body.get('carla_frame')!=state.get('frame') or
                body.get('time_s')!=video.get('time_s') or
                body.get('time_s')!=state.get('time_s')):
            raise ValueError('Saved body, camera and trace time join differs')
    measured=json.loads(json.dumps(measure_space(scene,frames)))
    if (report['measurements']['space_at_entry']['value']!=measured or
            result['measured_values']['space_at_entry']!=measured):
        raise ValueError('Saved entry-space measurement differs from originals')
    for name in SOURCES:
        if report['measurements']['space_at_entry']['sources'].get(name)!=sha(root/name):
            raise ValueError('Changed original delivery source: '+name)
    decode_dir=Path(decode_dir);decode_dir.mkdir(parents=True,exist_ok=True)
    mapping_sha=sha(root/'video_frames.jsonl')
    cameras={name:media.audit(root/(name+'.mkv'),len(mapping),mapping_sha256=mapping_sha,
                              receipt=decode_dir/('source-decode-'+name+'.json')) for name in CAMERAS}
    primary=media.audit(root/'raw.mkv',len(mapping),mapping_sha256=mapping_sha,
                        receipt=decode_dir/'source-decode-primary.json')
    if diagnostic_fixture:
        if not (root/'fixture-provenance.json').is_file():
            raise ValueError('Unmarked diagnostic fixture')
        physical=False
    else:
        seal=root/'capture-seal.json'
        review=root/'space-physical-pixel-review.json'
        if not seal.is_file() or not review.is_file():
            raise ValueError('Native seal and physical/pixel review missing')
        checked=json.loads(review.read_text())
        if (checked.get('case_id')!=case or not checked.get('reviewer') or
                not checked.get('both_participants_visible') or
                not checked.get('entry_and_passage_visible') or
                not checked.get('motion_completed')):
            raise ValueError('Native physical/pixel review incomplete')
        if any(checked.get('original_sha256',{}).get(name)!=sha(root/name) for name in SOURCES):
            raise ValueError('Native physical/pixel review source changed')
        physical=True
    return {'format':'worker-delivery-audit','case_id':case,'frames':len(mapping),
            'original_sha256':{name:sha(root/name) for name in SOURCES},
            'source_decode_receipt_path':str(decode_dir/'source-decode-primary.json'),
            'source_decode_receipt_sha256':sha(decode_dir/'source-decode-primary.json'),
            'source_decode_auditor_sha256':primary['auditor_sha256'],
            'cameras':cameras,
            'checks':{'native_source':physical,'all_participants':True,'time_join':True,
                      'full_video_decode':True,'actual_pixels':physical,
                      'physical_completion':physical},
            'physical_acceptance_claimed':False,'legal_acceptance_claimed':False}


def main():
    parser=argparse.ArgumentParser()
    for name in ('case','analysis','decode_dir','output'):
        parser.add_argument('--'+name.replace('_','-'),required=True)
    parser.add_argument('--diagnostic-fixture',action='store_true')
    args=parser.parse_args()
    result=audit(args.case,args.analysis,args.decode_dir,args.diagnostic_fixture)
    Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    print(result['case_id'],result['frames'])


if __name__=='__main__':
    main()
